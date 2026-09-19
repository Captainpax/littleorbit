"""Explicit offline-note recovery without overwriting newer shared content."""

import asyncio
import re
import shutil
from datetime import datetime
from pathlib import Path
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..attachment_models import NoteAttachment
from ..attachment_quota import reserve_storage
from ..attachment_storage import (
    COUPLE_QUOTA_BYTES,
    AttachmentPolicyError,
    available_path,
    has_upload_capacity,
    sha256_file,
)
from ..clock import SystemClock
from ..config import get_settings
from ..couple_access import active_member, lock_couple
from ..database import session_scope
from ..dependencies import current_account
from ..interaction_schemas import NoteForkRequest, NoteResponse
from ..models import Account, Note

router = APIRouter(tags=["notes"])
ATTACHMENT_REFERENCE = re.compile(r"attachment://([0-9a-fA-F-]{36})")


@router.post("/v1/notes/{note_id}/fork", response_model=NoteResponse)
async def fork_note(
    note_id: UUID,
    payload: NoteForkRequest,
    actor: Account = Depends(current_account),
    session: AsyncSession = Depends(session_scope),
) -> NoteResponse:
    """Save an explicit local conflict as a new note with valid clean attachments."""

    member = await active_member(session, actor.id)
    await lock_couple(session, member.couple_id)
    prior = await session.scalar(
        select(Note).where(
            Note.creation_operation_id == payload.operation_id,
            Note.couple_id == member.couple_id,
        )
    )
    if prior is not None:
        return _response(prior)
    source = await session.scalar(
        select(Note).where(Note.id == note_id, Note.couple_id == member.couple_id)
    )
    if source is None or source.archived_at is not None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Note is unavailable")
    attachments = await _referenced_attachments(session, source, payload.body)
    await _reserve_copy(session, member.couple_id, attachments)
    copied_paths: list[Path] = []
    try:
        note = await _copy_note(
            session, source, actor.id, payload, attachments, copied_paths
        )
        await session.commit()
    except Exception:
        await session.rollback()
        await _remove_paths(copied_paths)
        raise
    return _response(note)


async def _referenced_attachments(
    session: AsyncSession, source: Note, body: str
) -> list[NoteAttachment]:
    ids = {UUID(value) for value in ATTACHMENT_REFERENCE.findall(body)}
    if not ids:
        return []
    items = list(
        await session.scalars(
            select(NoteAttachment).where(
                NoteAttachment.id.in_(ids),
                NoteAttachment.note_id == source.id,
                NoteAttachment.couple_id == source.couple_id,
                NoteAttachment.status == "available",
                NoteAttachment.deleted_at.is_(None),
            )
        )
    )
    if {item.id for item in items} != ids:
        raise HTTPException(status.HTTP_409_CONFLICT, "Attachment mapping changed; refresh")
    return items


async def _reserve_copy(
    session: AsyncSession, couple_id: UUID, items: list[NoteAttachment]
) -> None:
    incoming = sum(item.size_bytes for item in items)
    if incoming == 0:
        return
    used = int(
        await session.scalar(
            select(func.coalesce(func.sum(NoteAttachment.size_bytes), 0)).where(
                NoteAttachment.couple_id == couple_id,
                NoteAttachment.deleted_at.is_(None),
                NoteAttachment.status.in_(("uploading", "pending_scan", "scanning", "available")),
            )
        )
        or 0
    )
    root = get_settings().attachment_storage_dir
    if used + incoming > COUPLE_QUOTA_BYTES:
        raise HTTPException(status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, "couple_quota_exceeded")
    if not await asyncio.to_thread(has_upload_capacity, root, incoming):
        raise HTTPException(status.HTTP_507_INSUFFICIENT_STORAGE, "attachment_storage_unavailable")
    try:
        await reserve_storage(session, incoming)
    except AttachmentPolicyError as error:
        raise HTTPException(status.HTTP_507_INSUFFICIENT_STORAGE, str(error)) from error


async def _copy_note(
    session: AsyncSession,
    source: Note,
    actor_id: UUID,
    payload: NoteForkRequest,
    attachments: list[NoteAttachment],
    copied: list[Path],
) -> Note:
    now = SystemClock().now()
    note = Note(
        creation_operation_id=payload.operation_id,
        couple_id=source.couple_id,
        title=payload.title,
        body=payload.body,
        revision=0,
        created_at=now,
        updated_at=now,
    )
    session.add(note)
    await session.flush()
    rewritten = payload.body
    for item in attachments:
        clone, target = await _copy_attachment(item, note.id, actor_id, now)
        session.add(clone)
        copied.append(target)
        rewritten = rewritten.replace(f"attachment://{item.id}", f"attachment://{clone.id}")
    note.body = rewritten
    return note


async def _copy_attachment(
    source: NoteAttachment, note_id: UUID, actor_id: UUID, now: datetime
) -> tuple[NoteAttachment, Path]:
    root = get_settings().attachment_storage_dir
    source_path = available_path(root, source.storage_key)
    if not source_path.is_file() or await asyncio.to_thread(sha256_file, source_path) != source.sha256:
        raise HTTPException(status.HTTP_409_CONFLICT, "Attachment bytes changed; refresh")
    clone_id = uuid4()
    storage_key = uuid4().hex
    target = available_path(root, storage_key)
    target.parent.mkdir(parents=True, exist_ok=True)
    await asyncio.to_thread(shutil.copyfile, source_path, target)
    if await asyncio.to_thread(sha256_file, target) != source.sha256:
        target.unlink(missing_ok=True)
        raise HTTPException(status.HTTP_409_CONFLICT, "Attachment copy verification failed")
    clone = NoteAttachment(
        id=clone_id,
        note_id=note_id,
        couple_id=source.couple_id,
        uploaded_by=actor_id,
        operation_id=uuid4(),
        file_name=source.file_name,
        media_type=source.media_type,
        size_bytes=source.size_bytes,
        uploaded_bytes=source.size_bytes,
        sha256=source.sha256,
        storage_key=storage_key,
        status="available",
        created_at=now,
        updated_at=now,
        scanned_at=now,
    )
    return clone, target


async def _remove_paths(paths: list[Path]) -> None:
    for path in paths:
        await asyncio.to_thread(path.unlink, missing_ok=True)


def _response(note: Note) -> NoteResponse:
    return NoteResponse(
        id=note.id,
        title=note.title,
        body=note.body,
        revision=note.revision,
        metadata_revision=note.metadata_revision,
        updated_at=note.updated_at,
        archived_at=note.archived_at,
        purge_after=note.purge_after,
    )
