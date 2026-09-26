"""Read-only attachment access for an authenticated former couple member."""

from pathlib import Path
from urllib.parse import quote
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..attachment_models import NoteAttachment
from ..attachment_responses import attachment_response
from ..attachment_schemas import AttachmentResponse
from ..attachment_storage import available_path
from ..config import get_settings
from ..couple_access import archived_member
from ..database import session_scope
from ..dependencies import current_account
from ..models import Account, Note

router = APIRouter(
    prefix="/v1/couple/archives/{archive_id}/notes/{note_id}/attachments",
    tags=["couple archives"],
)
ARCHIVE_UNAVAILABLE = "Archive is unavailable"


async def _authorized_note(
    session: AsyncSession, actor_id: UUID, archive_id: UUID, note_id: UUID
) -> Note:
    """Authorize the former membership before resolving a private note."""

    await archived_member(session, actor_id, archive_id)
    note = await session.scalar(
        select(Note).where(Note.id == note_id, Note.couple_id == archive_id)
    )
    if note is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, ARCHIVE_UNAVAILABLE)
    return note


async def _authorized_attachment(
    session: AsyncSession,
    actor_id: UUID,
    archive_id: UUID,
    note_id: UUID,
    attachment_id: UUID,
) -> NoteAttachment:
    """Resolve only a clean, published file after former-member authorization."""

    await _authorized_note(session, actor_id, archive_id, note_id)
    item = await session.scalar(
        select(NoteAttachment).where(
            NoteAttachment.id == attachment_id,
            NoteAttachment.note_id == note_id,
            NoteAttachment.couple_id == archive_id,
            NoteAttachment.status == "available",
            NoteAttachment.deleted_at.is_(None),
        )
    )
    if item is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, ARCHIVE_UNAVAILABLE)
    return item


def _response(item: NoteAttachment, archive_id: UUID) -> AttachmentResponse:
    route = (
        f"/api/v1/couple/archives/{archive_id}/notes/{item.note_id}"
        f"/attachments/{item.id}/content"
    )
    return attachment_response(item, download_url=route)


@router.get("", response_model=list[AttachmentResponse])
async def list_archive_attachments(
    archive_id: UUID,
    note_id: UUID,
    actor: Account = Depends(current_account),
    session: AsyncSession = Depends(session_scope),
) -> list[AttachmentResponse]:
    """List only clean files belonging to one authorized former-pairing note."""

    await _authorized_note(session, actor.id, archive_id, note_id)
    items = list(
        await session.scalars(
            select(NoteAttachment)
            .where(
                NoteAttachment.note_id == note_id,
                NoteAttachment.couple_id == archive_id,
                NoteAttachment.status == "available",
                NoteAttachment.deleted_at.is_(None),
            )
            .order_by(NoteAttachment.created_at)
        )
    )
    return [_response(item, archive_id) for item in items]


def _available_file(item: NoteAttachment) -> Path:
    path = available_path(get_settings().attachment_storage_dir, item.storage_key)
    if not path.is_file() or path.stat().st_size != item.size_bytes:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE, "Archive bytes are unavailable"
        )
    return path


@router.api_route(
    "/{attachment_id}/content",
    methods=["GET", "HEAD"],
    response_class=FileResponse,
)
async def download_archive_attachment(
    archive_id: UUID,
    note_id: UUID,
    attachment_id: UUID,
    request: Request,
    actor: Account = Depends(current_account),
    session: AsyncSession = Depends(session_scope),
) -> Response:
    """Serve verified-size sanitized bytes without restoring shared access."""

    item = await _authorized_attachment(
        session, actor.id, archive_id, note_id, attachment_id
    )
    path = _available_file(item)
    headers = {
        "Cache-Control": "private, no-store",
        "X-Content-Type-Options": "nosniff",
        "Content-Disposition": f"inline; filename*=UTF-8''{quote(item.file_name)}",
    }
    if request.method == "HEAD":
        headers["Content-Length"] = str(item.size_bytes)
        return Response(status_code=200, media_type=item.media_type, headers=headers)
    return FileResponse(path, media_type=item.media_type, filename=item.file_name, headers=headers)
