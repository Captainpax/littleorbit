"""Authorized in-app activity feed without private feature content."""

from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from ..activity_models import ActivityEvent, ActivitySeen
from ..activity_schemas import ActivityPage, ActivityResponse, ActivitySeenRequest
from ..clock import SystemClock
from ..couple_access import active_member, lock_couple
from ..database import session_scope
from ..dependencies import current_account
from ..models import Account

router = APIRouter(prefix="/v1/activity", tags=["activity"])


@router.get("", response_model=ActivityPage)
async def list_activity(
    cursor: int | None = Query(default=None, ge=0),
    limit: int = Query(default=30, ge=1, le=100),
    unread_only: bool = False,
    actor: Account = Depends(current_account),
    session: AsyncSession = Depends(session_scope),
) -> ActivityPage:
    """Return one newest-first page after active-couple authorization."""

    member = await active_member(session, actor.id)
    seen = await _seen_through(session, member.couple_id, actor.id)
    query = (
        select(ActivityEvent, Account.display_name)
        .outerjoin(Account, Account.id == ActivityEvent.actor_id)
        .where(ActivityEvent.couple_id == member.couple_id)
    )
    if cursor is not None:
        query = query.where(ActivityEvent.sequence < cursor)
    if unread_only:
        query = query.where(ActivityEvent.sequence > seen)
    rows = list((await session.execute(
        query.order_by(ActivityEvent.sequence.desc()).limit(limit + 1)
    )).all())
    more = len(rows) > limit
    rows = rows[:limit]
    items = [_response(event, name, actor.id, seen) for event, name in rows]
    return ActivityPage(
        items=items,
        next_cursor=items[-1].sequence if more and items else None,
        seen_through=seen,
    )


@router.put("/seen", response_model=None, status_code=204)
async def mark_activity_seen(
    payload: ActivitySeenRequest,
    actor: Account = Depends(current_account),
    session: AsyncSession = Depends(session_scope),
) -> None:
    """Advance the member watermark without allowing future sequences."""

    member = await active_member(session, actor.id)
    await lock_couple(session, member.couple_id)
    highest = await session.scalar(
        select(func.coalesce(func.max(ActivityEvent.sequence), 0)).where(
            ActivityEvent.couple_id == member.couple_id
        )
    )
    through = min(payload.through_sequence, int(highest or 0))
    now = SystemClock().now()
    await session.execute(
        insert(ActivitySeen)
        .values(
            id=uuid4(), couple_id=member.couple_id, account_id=actor.id,
            through_sequence=through, updated_at=now,
        )
        .on_conflict_do_update(
            index_elements=["couple_id", "account_id"],
            set_={
                "through_sequence": func.greatest(ActivitySeen.through_sequence, through),
                "updated_at": now,
            },
        )
    )
    await session.commit()


async def _seen_through(session: AsyncSession, couple_id: UUID, account_id: UUID) -> int:
    value = await session.scalar(
        select(ActivitySeen.through_sequence).where(
            ActivitySeen.couple_id == couple_id,
            ActivitySeen.account_id == account_id,
        )
    )
    return int(value or 0)


def _response(
    event: ActivityEvent, actor_name: str | None, viewer_id: UUID, seen: int
) -> ActivityResponse:
    return ActivityResponse(
        id=event.id,
        sequence=event.sequence,
        kind=event.kind,
        partner_display_name="You" if event.actor_id == viewer_id else actor_name or "Partner",
        target_type=event.target_type,
        target_id=event.target_id,
        target_title=event.target_title,
        emoji=event.emoji,
        created_at=event.created_at,
        seen=event.sequence <= seen,
    )
