"""Transactional helpers for content-free couple activity events."""

from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from .activity_models import ActivityEvent
from .activity_schemas import ActivityEmoji, ActivityKind, ActivityTargetType
from .clock import SystemClock


async def record_activity(
    session: AsyncSession,
    couple_id: UUID,
    actor_id: UUID | None,
    kind: ActivityKind,
    dedupe_key: str,
    *,
    target_type: ActivityTargetType | None = None,
    target_id: UUID | None = None,
    target_title: str | None = None,
    emoji: ActivityEmoji | None = None,
) -> None:
    """Append one idempotent event while the caller holds the couple lock."""

    prior = await session.scalar(
        select(ActivityEvent.id).where(
            ActivityEvent.couple_id == couple_id,
            ActivityEvent.dedupe_key == dedupe_key,
        )
    )
    if prior is not None:
        return
    current = await session.scalar(
        select(func.coalesce(func.max(ActivityEvent.sequence), 0)).where(
            ActivityEvent.couple_id == couple_id
        )
    )
    session.add(
        ActivityEvent(
            couple_id=couple_id,
            actor_id=actor_id,
            sequence=int(current or 0) + 1,
            dedupe_key=dedupe_key,
            kind=kind,
            target_type=target_type,
            target_id=target_id,
            target_title=target_title,
            emoji=emoji,
            created_at=SystemClock().now(),
        )
    )
