"""Construct privacy-safe attachment metadata with caller-owned routes."""

from .attachment_models import NoteAttachment
from .attachment_schemas import AttachmentResponse


def attachment_response(
    item: NoteAttachment, *, download_url: str | None
) -> AttachmentResponse:
    """Return public metadata without exposing a storage key or filesystem path."""

    return AttachmentResponse(
        id=item.id,
        note_id=item.note_id,
        file_name=item.file_name,
        media_type=item.media_type,
        size_bytes=item.size_bytes,
        uploaded_bytes=item.uploaded_bytes,
        sha256=item.sha256,
        status=item.status,
        rejection_reason=item.rejection_reason,
        download_url=download_url,
        created_at=item.created_at,
        updated_at=item.updated_at,
    )
