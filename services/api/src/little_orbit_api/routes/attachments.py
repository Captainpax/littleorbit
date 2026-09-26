"""Authorized resumable upload and download routes for note attachments."""

import asyncio
import os
from pathlib import Path
from typing import cast
from urllib.parse import quote
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, Header, HTTPException, Request, Response, status
from fastapi.responses import FileResponse
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..attachment_models import AttachmentJob, NoteAttachment
from ..attachment_quota import adjust_storage, reserve_storage
from ..attachment_responses import attachment_response
from ..attachment_schemas import (
    AttachmentCreateRequest,
    AttachmentResponse,
    AttachmentUploadResponse,
)
from ..attachment_storage import (
    COUPLE_QUOTA_BYTES,
    MAX_CHUNK_BYTES,
    MAX_CONCURRENT_UPLOADS_PER_COUPLE,
    AttachmentPolicyError,
    available_path,
    has_upload_capacity,
    processing_path,
    safe_file_name,
    sha256_file,
    staging_path,
    validate_chunk,
    validate_metadata,
)
from ..clock import SystemClock
from ..config import get_settings
from ..couple_access import active_member, lock_couple
from ..database import session_scope
from ..dependencies import current_account
from ..models import Account, CoupleMember, Note

router = APIRouter(tags=["note attachments"])


def _response(item: NoteAttachment) -> AttachmentResponse:
    download_url = (
        f"/api/v1/notes/{item.note_id}/attachments/{item.id}/content"
        if item.status == "available"
        else None
    )
    return attachment_response(item, download_url=download_url)


async def _authorized_note(
    session: AsyncSession, actor_id: UUID, note_id: UUID, *, include_archived: bool = False
) -> tuple[CoupleMember, Note]:
    """Authorize the actor before resolving a couple-scoped note."""

    member = await active_member(session, actor_id)
    query = select(Note).where(Note.id == note_id, Note.couple_id == member.couple_id)
    if not include_archived:
        query = query.where(Note.archived_at.is_(None))
    note = await session.scalar(query)
    if note is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Note is unavailable")
    return member, note


async def _authorized_attachment(
    session: AsyncSession, actor_id: UUID, note_id: UUID, attachment_id: UUID
) -> NoteAttachment:
    """Authorize membership and note ownership before attachment lookup."""

    member, _ = await _authorized_note(session, actor_id, note_id)
    item = await session.scalar(
        select(NoteAttachment).where(
            NoteAttachment.id == attachment_id,
            NoteAttachment.note_id == note_id,
            NoteAttachment.couple_id == member.couple_id,
            NoteAttachment.deleted_at.is_(None),
        )
    )
    if item is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Attachment is unavailable")
    return item


@router.get("/v1/notes/{note_id}/attachments", response_model=list[AttachmentResponse])
async def list_attachments(
    note_id: UUID,
    actor: Account = Depends(current_account),
    session: AsyncSession = Depends(session_scope),
) -> list[AttachmentResponse]:
    """List attachment state only for a current authorized couple."""

    member, _ = await _authorized_note(session, actor.id, note_id)
    items = list(
        await session.scalars(
            select(NoteAttachment)
            .where(
                NoteAttachment.note_id == note_id,
                NoteAttachment.couple_id == member.couple_id,
                NoteAttachment.deleted_at.is_(None),
            )
            .order_by(NoteAttachment.created_at)
        )
    )
    return [_response(item) for item in items]


@router.post(
    "/v1/notes/{note_id}/attachments",
    response_model=AttachmentUploadResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_attachment(
    note_id: UUID,
    payload: AttachmentCreateRequest,
    actor: Account = Depends(current_account),
    session: AsyncSession = Depends(session_scope),
) -> AttachmentUploadResponse:
    """Reserve quota and return a stable offset upload target idempotently."""

    member, note = await _authorized_note(session, actor.id, note_id)
    await lock_couple(session, member.couple_id)
    file_name = _validated_file_name(payload)
    prior = await _prior_upload(session, note.id, payload.operation_id)
    if prior is not None:
        if not _same_upload(prior, payload, file_name):
            raise HTTPException(status.HTTP_409_CONFLICT, "operation_id_payload_mismatch")
        return _upload_response(prior)
    await _reserve_upload_capacity(session, member.couple_id, payload.size_bytes)
    item = _new_attachment(note.id, member.couple_id, actor.id, payload, file_name)
    session.add(item)
    await session.commit()
    return _upload_response(item)


def _validated_file_name(payload: AttachmentCreateRequest) -> str:
    try:
        validate_metadata(payload.media_type, payload.size_bytes, payload.sha256)
        return safe_file_name(payload.file_name)
    except AttachmentPolicyError as error:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(error)) from error


async def _prior_upload(
    session: AsyncSession, note_id: UUID, operation_id: UUID
) -> NoteAttachment | None:
    result = await session.scalar(
        select(NoteAttachment).where(
            NoteAttachment.note_id == note_id,
            NoteAttachment.operation_id == operation_id,
        )
    )
    return cast(NoteAttachment | None, result)


async def _reserve_upload_capacity(
    session: AsyncSession, couple_id: UUID, size_bytes: int
) -> None:
    concurrent = await session.scalar(
        select(func.count()).select_from(NoteAttachment).where(
            NoteAttachment.couple_id == couple_id,
            NoteAttachment.deleted_at.is_(None),
            NoteAttachment.status == "uploading",
        )
    )
    if int(concurrent or 0) >= MAX_CONCURRENT_UPLOADS_PER_COUPLE:
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, "too_many_active_uploads")
    reserved = await session.scalar(
        select(func.coalesce(func.sum(NoteAttachment.size_bytes), 0)).where(
            NoteAttachment.couple_id == couple_id,
            NoteAttachment.deleted_at.is_(None),
            NoteAttachment.status.in_(("uploading", "pending_scan", "scanning", "available")),
        )
    )
    if int(reserved or 0) + size_bytes > COUPLE_QUOTA_BYTES:
        raise HTTPException(status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, "couple_quota_exceeded")
    storage_root = get_settings().attachment_storage_dir
    capacity = await asyncio.to_thread(has_upload_capacity, storage_root, size_bytes)
    if not capacity:
        raise HTTPException(
            status.HTTP_507_INSUFFICIENT_STORAGE, "attachment_storage_unavailable"
        )
    try:
        await reserve_storage(session, size_bytes)
    except AttachmentPolicyError as error:
        raise HTTPException(status.HTTP_507_INSUFFICIENT_STORAGE, str(error)) from error


def _new_attachment(
    note_id: UUID,
    couple_id: UUID,
    actor_id: UUID,
    payload: AttachmentCreateRequest,
    file_name: str,
) -> NoteAttachment:
    now = SystemClock().now()
    return NoteAttachment(
        note_id=note_id,
        couple_id=couple_id,
        uploaded_by=actor_id,
        operation_id=payload.operation_id,
        file_name=file_name,
        media_type=payload.media_type,
        size_bytes=payload.size_bytes,
        sha256=payload.sha256,
        storage_key=uuid4().hex,
        created_at=now,
        updated_at=now,
    )


def _upload_response(item: NoteAttachment) -> AttachmentUploadResponse:
    return AttachmentUploadResponse(
        attachment=_response(item),
        upload_url=f"/api/v1/notes/{item.note_id}/attachments/{item.id}/content",
    )


def _same_upload(
    item: NoteAttachment, payload: AttachmentCreateRequest, file_name: str
) -> bool:
    """Require idempotency-key replays to describe the exact same bytes."""

    return (
        item.file_name == file_name
        and item.media_type == payload.media_type
        and item.size_bytes == payload.size_bytes
        and item.sha256 == payload.sha256
    )


@router.put(
    "/v1/notes/{note_id}/attachments/{attachment_id}/content",
    response_model=AttachmentResponse,
)
async def upload_attachment_chunk(
    note_id: UUID,
    attachment_id: UUID,
    request: Request,
    upload_offset: int = Header(alias="Upload-Offset", ge=0),
    actor: Account = Depends(current_account),
    session: AsyncSession = Depends(session_scope),
) -> AttachmentResponse:
    """Append exactly one bounded chunk at the server-advertised offset."""

    authorized = await _authorized_attachment(session, actor.id, note_id, attachment_id)
    await lock_couple(session, authorized.couple_id)
    item = await session.scalar(
        select(NoteAttachment).where(NoteAttachment.id == attachment_id).with_for_update()
    )
    if item is None or item.status != "uploading":
        raise HTTPException(status.HTTP_409_CONFLICT, "attachment_not_uploading")
    if upload_offset != item.uploaded_bytes:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "upload_offset_mismatch",
            headers={"Upload-Offset": str(item.uploaded_bytes)},
        )
    body = await _read_chunk(request)
    try:
        validate_chunk(upload_offset, len(body), item.size_bytes)
    except AttachmentPolicyError as error:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(error)) from error
    target = staging_path(get_settings().attachment_storage_dir, item.storage_key)
    try:
        await asyncio.to_thread(_append_chunk, target, upload_offset, body)
    except AttachmentPolicyError as error:
        raise HTTPException(status.HTTP_409_CONFLICT, str(error)) from error
    item.uploaded_bytes += len(body)
    item.updated_at = SystemClock().now()
    if item.uploaded_bytes == item.size_bytes:
        actual_hash = await asyncio.to_thread(sha256_file, target)
        if actual_hash != item.sha256:
            await adjust_storage(session, -item.size_bytes)
            item.status = "rejected"
            item.rejection_reason = "sha256_mismatch"
            await asyncio.to_thread(target.unlink, True)
        else:
            item.status = "pending_scan"
            now = SystemClock().now()
            session.add(
                AttachmentJob(
                    attachment_id=item.id,
                    status="pending",
                    attempts=0,
                    next_attempt_at=now,
                    created_at=now,
                    updated_at=now,
                )
            )
    await session.commit()
    return _response(item)


async def _read_chunk(request: Request) -> bytes:
    """Read at most one protocol chunk without buffering an unbounded request body."""

    declared = request.headers.get("content-length")
    if declared is not None:
        try:
            if int(declared) > MAX_CHUNK_BYTES:
                raise HTTPException(status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, "chunk_too_large")
        except ValueError as error:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "invalid_content_length") from error
    body = bytearray()
    async for part in request.stream():
        body.extend(part)
        if len(body) > MAX_CHUNK_BYTES:
            raise HTTPException(status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, "chunk_too_large")
    return bytes(body)


def _append_chunk(target: Path, offset: int, body: bytes) -> None:
    """Append to one server-generated path while enforcing the locked offset."""

    target.parent.mkdir(parents=True, exist_ok=True)
    mode = "r+b" if target.exists() else "wb"
    with target.open(mode) as output:
        output.seek(0, 2)
        stored_offset = output.tell()
        if stored_offset < offset:
            raise AttachmentPolicyError("stored_offset_mismatch")
        if stored_offset > offset:
            output.truncate(offset)
            output.seek(offset)
        output.write(body)
        output.flush()
        os.fsync(output.fileno())


@router.api_route(
    "/v1/notes/{note_id}/attachments/{attachment_id}/content",
    methods=["GET", "HEAD"],
    response_class=FileResponse,
)
async def download_attachment(
    note_id: UUID,
    attachment_id: UUID,
    request: Request,
    actor: Account = Depends(current_account),
    session: AsyncSession = Depends(session_scope),
) -> Response:
    """Serve sanitized bytes after current authorization and a clean scan."""

    item = await _authorized_attachment(session, actor.id, note_id, attachment_id)
    if item.status != "available":
        raise HTTPException(status.HTTP_409_CONFLICT, "attachment_not_available")
    path = available_path(get_settings().attachment_storage_dir, item.storage_key)
    if not path.is_file() or path.stat().st_size != item.size_bytes:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "attachment_bytes_unavailable")
    headers = {
        "Cache-Control": "private, no-store",
        "X-Content-Type-Options": "nosniff",
        "Content-Disposition": f"inline; filename*=UTF-8''{quote(item.file_name)}",
    }
    if request.method == "HEAD":
        headers["Content-Length"] = str(item.size_bytes)
        return Response(status_code=200, media_type=item.media_type, headers=headers)
    return FileResponse(path, media_type=item.media_type, filename=item.file_name, headers=headers)


@router.delete(
    "/v1/notes/{note_id}/attachments/{attachment_id}", status_code=status.HTTP_204_NO_CONTENT
)
async def delete_attachment(
    note_id: UUID,
    attachment_id: UUID,
    actor: Account = Depends(current_account),
    session: AsyncSession = Depends(session_scope),
) -> Response:
    """Hide an attachment immediately and remove its private bytes."""

    item = await _authorized_attachment(session, actor.id, note_id, attachment_id)
    await lock_couple(session, item.couple_id)
    if item.status in {"uploading", "pending_scan", "scanning", "available"}:
        await adjust_storage(session, -item.size_bytes)
    item.deleted_at = SystemClock().now()
    item.status = "deleted"
    item.updated_at = item.deleted_at
    await session.commit()
    root = get_settings().attachment_storage_dir
    await asyncio.gather(
        asyncio.to_thread(staging_path(root, item.storage_key).unlink, True),
        asyncio.to_thread(processing_path(root, item.storage_key).unlink, True),
        asyncio.to_thread(available_path(root, item.storage_key).unlink, True),
    )
    return Response(status_code=status.HTTP_204_NO_CONTENT)
