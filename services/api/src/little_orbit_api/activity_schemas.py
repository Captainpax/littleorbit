"""Strict, content-free contracts for the in-app activity feed."""

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import Field

from .schema_base import StrictModel

ActivityKind = Literal[
    "note_created",
    "note_updated",
    "attachment_available",
    "countdown_created",
    "countdown_updated",
    "quiz_submitted",
    "quiz_revealed",
    "smooch_received",
]
ActivityTargetType = Literal["note", "countdown", "quiz", "smooch"]
ActivityEmoji = Literal["😘", "😍", "🤭", "😈", "🔥", "👀", "💖", "🐻", "🍑"]


class ActivityResponse(StrictModel):
    """One authorized event without relationship content."""

    id: UUID
    sequence: int = Field(ge=1)
    kind: ActivityKind
    partner_display_name: str = Field(min_length=1, max_length=120)
    target_type: ActivityTargetType | None
    target_id: UUID | None
    target_title: str | None = Field(default=None, min_length=1, max_length=120)
    emoji: ActivityEmoji | None
    created_at: datetime
    seen: bool


class ActivityPage(StrictModel):
    """Cursor page and the member's current seen watermark."""

    items: list[ActivityResponse] = Field(max_length=100)
    next_cursor: int | None = Field(default=None, ge=1)
    seen_through: int = Field(ge=0)


class ActivitySeenRequest(StrictModel):
    """Retry-safe monotonic visible-event acknowledgement."""

    through_sequence: int = Field(ge=0)
    operation_id: UUID
