"""Strict request and response contracts for private note attachments."""

from datetime import datetime
from typing import Annotated
from uuid import UUID

from pydantic import Field

from .schema_base import StrictModel, StrictText


class AttachmentCreateRequest(StrictModel):
    """Start or resume one content-addressed attachment upload."""

    operation_id: UUID
    file_name: Annotated[StrictText, Field(min_length=1, max_length=255)]
    media_type: Annotated[StrictText, Field(min_length=1, max_length=80)]
    size_bytes: int = Field(gt=0, le=104_857_600)
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")


class AttachmentResponse(StrictModel):
    """Privacy-safe attachment metadata visible to the active couple."""

    id: UUID
    note_id: UUID
    file_name: str
    media_type: str
    size_bytes: int
    uploaded_bytes: int
    sha256: str
    status: str
    rejection_reason: str | None
    download_url: str | None
    created_at: datetime
    updated_at: datetime


class AttachmentUploadResponse(StrictModel):
    """Current upload offset and stable versioned target."""

    attachment: AttachmentResponse
    upload_url: str
    chunk_size_bytes: int = 1_048_576
