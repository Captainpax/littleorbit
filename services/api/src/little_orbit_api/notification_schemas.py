"""Versioned self-hosted notification request and response contracts."""

from datetime import datetime
from typing import Annotated, Literal
from uuid import UUID

from pydantic import Field

from .schema_base import StrictModel


class NotificationPreferencesResponse(StrictModel):
    """Account-wide notification choices."""

    master_enabled: bool
    smooches_enabled: bool
    note_editing_enabled: bool
    daily_quiz_enabled: bool
    countdowns_enabled: bool
    weekly_summary_enabled: bool
    updated_at: datetime


class NotificationPreferencesUpdate(StrictModel):
    """A complete replacement used to avoid ambiguous partial preference state."""

    master_enabled: bool
    smooches_enabled: bool
    note_editing_enabled: bool
    daily_quiz_enabled: bool
    countdowns_enabled: bool
    weekly_summary_enabled: bool


class NotificationDeviceUpsert(StrictModel):
    """Non-hardware installation metadata needed for delivery diagnostics."""

    platform: Literal["android"]
    app_version_code: int = Field(ge=1, le=2_147_483_647)
    notifications_enabled: bool


class NotificationDeviceResponse(StrictModel):
    """Registered state for the caller's random installation identifier."""

    device_id: UUID
    last_seen_at: datetime
    notifications_enabled: bool


class NotificationEventResponse(StrictModel):
    """One authorized alert payload with no note body or attachment metadata."""

    id: UUID
    kind: Literal["smooch_received", "note_editing"]
    created_at: datetime
    expires_at: datetime
    actor_display_name: str | None = Field(default=None, max_length=80)
    emoji: str | None = Field(default=None, max_length=16)
    phrase_key: str | None = Field(default=None, max_length=32)
    note_id: UUID | None = None
    note_title: str | None = Field(default=None, max_length=120)


class NotificationDeliveryAck(StrictModel):
    """Bounded per-installation acknowledgement after Android displayed alerts."""

    device_id: UUID
    event_ids: Annotated[list[UUID], Field(min_length=1, max_length=50)]
