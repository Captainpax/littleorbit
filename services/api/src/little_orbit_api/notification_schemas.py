"""Versioned self-hosted notification request and response contracts."""

from datetime import date, datetime
from typing import Annotated, Literal
from uuid import UUID

from pydantic import Field

from .schema_base import StrictModel

NotificationKind = Literal[
    "smooch_received",
    "note_editing",
    "countdown_created",
    "countdown_rescheduled",
    "quiz_available",
    "quiz_partner_finished",
    "quiz_results_ready",
    "together_time_corrected",
]


class NotificationPreferencesResponse(StrictModel):
    """Account-wide notification choices."""

    master_enabled: bool
    smooches_enabled: bool
    note_editing_enabled: bool
    daily_quiz_enabled: bool
    countdowns_enabled: bool
    together_time_enabled: bool
    weekly_summary_enabled: bool
    updated_at: datetime


class NotificationPreferencesUpdate(StrictModel):
    """A complete replacement used to avoid ambiguous partial preference state."""

    master_enabled: bool
    smooches_enabled: bool
    note_editing_enabled: bool
    daily_quiz_enabled: bool
    countdowns_enabled: bool
    together_time_enabled: bool
    weekly_summary_enabled: bool


class NotificationDeviceUpsert(StrictModel):
    """Non-hardware installation metadata needed for delivery diagnostics."""

    platform: Literal["android"]
    app_version_code: int = Field(ge=1, le=2_147_483_647)
    notifications_enabled: bool
    push_token: str | None = Field(default=None, min_length=20, max_length=4096, pattern=r"^\S+$")


class NotificationDeviceResponse(StrictModel):
    """Registered state for the caller's random installation identifier."""

    device_id: UUID
    last_seen_at: datetime
    notifications_enabled: bool
    push_enabled: bool


class NotificationEventResponse(StrictModel):
    """One authorized alert payload with no note body or attachment metadata."""

    id: UUID
    kind: NotificationKind
    created_at: datetime
    expires_at: datetime
    actor_display_name: str | None = Field(default=None, max_length=80)
    emoji: str | None = Field(default=None, max_length=16)
    phrase_key: str | None = Field(default=None, max_length=32)
    note_id: UUID | None = None
    note_title: str | None = Field(default=None, max_length=120)
    countdown_id: UUID | None = None
    countdown_title: str | None = Field(default=None, max_length=120)
    quiz_date: date | None = None
    together_day: date | None = None


class NotificationDeliveryAck(StrictModel):
    """Bounded per-installation acknowledgement after Android displayed alerts."""

    device_id: UUID
    event_ids: Annotated[list[UUID], Field(min_length=1, max_length=50)]
