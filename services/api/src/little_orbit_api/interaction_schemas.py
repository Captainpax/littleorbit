"""Versioned note-workspace and Smooch request and response schemas."""

from datetime import date, datetime
from typing import Annotated
from uuid import UUID

from pydantic import Field

from .schema_base import StrictModel, StrictText


class NoteCreateRequest(StrictModel):
    """Idempotent shared note creation request."""

    operation_id: UUID
    title: Annotated[StrictText, Field(min_length=1, max_length=120)]
    body: Annotated[str, Field(max_length=100_000)] = ""


class NoteResponse(StrictModel):
    """Current shared note body, metadata, and lifecycle revisions."""

    id: UUID
    title: str
    body: str
    revision: int
    metadata_revision: int
    updated_at: datetime
    archived_at: datetime | None
    purge_after: datetime | None


class NoteTitleRequest(StrictModel):
    """Retry-safe title mutation independent of the body OT stream."""

    operation_id: UUID
    expected_metadata_revision: int = Field(ge=0)
    title: Annotated[StrictText, Field(min_length=1, max_length=120)]


class NoteArchiveRequest(StrictModel):
    """Retry-safe archive or restore request."""

    operation_id: UUID
    expected_metadata_revision: int = Field(ge=0)


class NoteForkRequest(StrictModel):
    """Idempotent explicit recovery of an offline version as a separate note."""

    operation_id: UUID
    title: Annotated[StrictText, Field(min_length=1, max_length=120)]
    body: Annotated[str, Field(max_length=100_000)]


class SmoochCreateRequest(StrictModel):
    """Retry-safe selection from the fixed RC10 emoji vocabulary."""

    operation_id: UUID
    emoji: Annotated[StrictText, Field(min_length=1, max_length=16)]


class SmoochResponse(StrictModel):
    """One authorized Smooch without unrelated relationship content."""

    id: UUID
    emoji: str
    phrase_key: str
    partner_display_name: str
    sent_at: datetime
    remaining_this_hour: int


class SmoochDelivery(StrictModel):
    """A pending notification payload for the intended recipient."""

    id: UUID
    emoji: str
    phrase_key: str
    partner_display_name: str
    sent_at: datetime


class SmoochDeliveryAck(StrictModel):
    """Bounded acknowledgement for notifications rendered on this device."""

    smooch_ids: Annotated[list[UUID], Field(min_length=1, max_length=50)]


class SmoochWeekSummary(StrictModel):
    """One calendar week in the couple's configured home timezone."""

    week_start: date
    week_end: date
    sent: int
    received: int
    combined: int
    emoji_counts: dict[str, int]


class SmoochStatus(StrictModel):
    """Current send capacity and warm shared recap for the dedicated tab."""

    partner_display_name: str
    remaining_this_hour: int = Field(ge=0, le=5)
    current_week: SmoochWeekSummary


class NoteHistoryEntry(StrictModel):
    """Applied note operation for revision history and reconciliation."""

    operation_id: UUID
    actor_id: UUID | None
    base_revision: int
    resulting_revision: int
    edit: dict[str, object]
    applied_at: datetime
