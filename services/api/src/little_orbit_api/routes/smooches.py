"""Authorized, retry-safe Smooch delivery and durable weekly history."""

from datetime import date, datetime, timedelta
from typing import cast
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from ..activity_schemas import ActivityEmoji
from ..activity_service import record_activity
from ..clock import SystemClock
from ..couple_access import active_member, lock_couple, relationship_inactive_error
from ..database import session_scope
from ..dependencies import current_account
from ..interaction_models import Smooch
from ..interaction_schemas import (
    SmoochCreateRequest,
    SmoochDelivery,
    SmoochDeliveryAck,
    SmoochResponse,
    SmoochStatus,
    SmoochWeekSummary,
)
from ..models import Account, Couple, CoupleMember
from ..notification_hub import NotificationConnectionHub
from ..notification_models import NotificationEvent
from ..notification_service import enqueue_smooch_event
from ..relationship_name_service import visible_relationship_names
from ..smooch_service import (
    EMOJIS,
    HOURLY_LIMIT,
    choose_phrase,
    retry_after_seconds,
    week_bounds_utc,
    week_start,
)

router = APIRouter(prefix="/v1/smooches", tags=["smooches"])


async def _partner(session: AsyncSession, member: CoupleMember) -> Account:
    partner = await session.scalar(
        select(Account)
        .join(CoupleMember, CoupleMember.account_id == Account.id)
        .where(
            CoupleMember.couple_id == member.couple_id,
            CoupleMember.account_id != member.account_id,
            CoupleMember.left_at.is_(None),
        )
    )
    if partner is None:
        raise relationship_inactive_error()
    return partner


async def _visible_partner_name(
    session: AsyncSession, member: CoupleMember, partner_id: UUID
) -> str:
    names = await visible_relationship_names(
        session, member.couple_id, (partner_id,), member.account_id
    )
    return names[partner_id].display_name


@router.post("", response_model=SmoochResponse, status_code=status.HTTP_201_CREATED)
async def send_smooch(
    payload: SmoochCreateRequest,
    request: Request,
    response: Response,
    actor: Account = Depends(current_account),
    session: AsyncSession = Depends(session_scope),
) -> SmoochResponse:
    """Send one fixed emoji while serializing rolling-limit and retry checks."""

    member = await active_member(session, actor.id)
    await lock_couple(session, member.couple_id)
    partner = await _partner(session, member)
    partner_name = await _visible_partner_name(session, member, partner.id)
    prior = await session.scalar(
        select(Smooch).where(
            Smooch.couple_id == member.couple_id,
            Smooch.sender_id == actor.id,
            Smooch.operation_id == payload.operation_id,
        )
    )
    now = SystemClock().now()
    recent = await _recent_sends(session, member.couple_id, actor.id, now)
    if prior is not None:
        return _send_response(prior, partner_name, len(recent))
    _enforce_send_allowed(payload.emoji, recent, now)
    smooch = Smooch(
        operation_id=payload.operation_id,
        couple_id=member.couple_id,
        sender_id=actor.id,
        recipient_id=partner.id,
        emoji=payload.emoji,
        phrase_key=choose_phrase(payload.operation_id),
        sent_at=now,
    )
    session.add(smooch)
    await session.flush()
    await record_activity(
        session,
        member.couple_id,
        actor.id,
        "smooch_received",
        f"smooch:{payload.operation_id}",
        target_type="smooch",
        target_id=smooch.id,
        emoji=cast(ActivityEmoji, smooch.emoji),
    )
    notified_account = await enqueue_smooch_event(session, smooch)
    await session.commit()
    if notified_account is not None:
        hub: NotificationConnectionHub = request.app.state.notification_connections
        await hub.available(notified_account)
    response.headers["X-RateLimit-Remaining"] = str(HOURLY_LIMIT - len(recent) - 1)
    return _send_response(smooch, partner_name, len(recent) + 1)


def _enforce_send_allowed(emoji: str, recent: list[datetime], now: datetime) -> None:
    if emoji not in EMOJIS:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Emoji is unavailable")
    retry = retry_after_seconds(recent, now)
    if retry:
        raise HTTPException(
            status.HTTP_429_TOO_MANY_REQUESTS,
            "Five Smooches are allowed in a rolling hour",
            headers={"Retry-After": str(retry)},
        )


async def _recent_sends(
    session: AsyncSession, couple_id: UUID, sender_id: UUID, now: datetime
) -> list[datetime]:
    """Return this sender's rolling-hour timestamps under the couple lock."""

    return list(
        await session.scalars(
            select(Smooch.sent_at).where(
                Smooch.couple_id == couple_id,
                Smooch.sender_id == sender_id,
                Smooch.sent_at > now - timedelta(hours=1),
            )
        )
    )


def _send_response(smooch: Smooch, partner_name: str, count: int) -> SmoochResponse:
    return SmoochResponse(
        id=smooch.id,
        emoji=smooch.emoji,
        phrase_key=smooch.phrase_key,
        partner_display_name=partner_name,
        sent_at=smooch.sent_at,
        remaining_this_hour=max(0, HOURLY_LIMIT - count),
    )


@router.get("/status", response_model=SmoochStatus)
async def smooch_status(
    actor: Account = Depends(current_account),
    session: AsyncSession = Depends(session_scope),
) -> SmoochStatus:
    """Return current rolling capacity and this week without exposing message content."""

    member = await active_member(session, actor.id)
    partner = await _partner(session, member)
    partner_name = await _visible_partner_name(session, member, partner.id)
    couple = await session.get(Couple, member.couple_id)
    if couple is None or couple.ended_at is not None:
        raise relationship_inactive_error()
    now = SystemClock().now()
    recent = list(
        await session.scalars(
            select(Smooch.sent_at).where(
                Smooch.couple_id == member.couple_id,
                Smooch.sender_id == actor.id,
                Smooch.sent_at > now - timedelta(hours=1),
            )
        )
    )
    start = week_start(now, couple.home_timezone)
    lower, upper = week_bounds_utc(start, couple.home_timezone)
    rows = list(
        await session.scalars(
            select(Smooch).where(
                Smooch.couple_id == member.couple_id,
                Smooch.sent_at >= lower,
                Smooch.sent_at < upper,
            )
        )
    )
    return SmoochStatus(
        partner_display_name=partner_name,
        remaining_this_hour=max(0, HOURLY_LIMIT - len(recent)),
        current_week=_week_summary(rows, actor.id, start, couple.home_timezone),
    )


@router.get("/pending", response_model=list[SmoochDelivery])
async def pending_smooches(
    actor: Account = Depends(current_account),
    session: AsyncSession = Depends(session_scope),
) -> list[SmoochDelivery]:
    """Return a bounded oldest-first notification queue for this recipient."""

    member = await active_member(session, actor.id)
    await lock_couple(session, member.couple_id)
    rows = list(
        await session.scalars(
            select(Smooch)
            .where(
                Smooch.couple_id == member.couple_id,
                Smooch.recipient_id == actor.id,
                Smooch.delivered_at.is_(None),
            )
            .order_by(Smooch.sent_at)
            .limit(50)
        )
    )
    names = await visible_relationship_names(
        session,
        member.couple_id,
        (item.sender_id for item in rows if item.sender_id is not None),
        actor.id,
    )
    return [
        SmoochDelivery(
            id=item.id,
            emoji=item.emoji,
            phrase_key=item.phrase_key,
            partner_display_name=names[item.sender_id].display_name,
            sent_at=item.sent_at,
        )
        for item in rows
        if item.sender_id in names
    ]


@router.post("/deliveries/ack", status_code=status.HTTP_204_NO_CONTENT)
async def acknowledge_deliveries(
    payload: SmoochDeliveryAck,
    actor: Account = Depends(current_account),
    session: AsyncSession = Depends(session_scope),
) -> None:
    """Mark only this member's current-couple Smooches as displayed."""

    member = await active_member(session, actor.id)
    await lock_couple(session, member.couple_id)
    await session.execute(
        update(Smooch)
        .where(
            Smooch.id.in_(payload.smooch_ids),
            Smooch.couple_id == member.couple_id,
            Smooch.recipient_id == actor.id,
            Smooch.delivered_at.is_(None),
        )
        .values(delivered_at=SystemClock().now())
    )
    await session.execute(
        update(NotificationEvent)
        .where(
            NotificationEvent.kind == "smooch_received",
            NotificationEvent.source_id.in_(payload.smooch_ids),
            NotificationEvent.recipient_id == actor.id,
            NotificationEvent.couple_id == member.couple_id,
            NotificationEvent.legacy_consumed_at.is_(None),
        )
        .values(legacy_consumed_at=SystemClock().now())
    )
    await session.commit()


@router.get("/weeks", response_model=list[SmoochWeekSummary])
async def smooch_weeks(
    weeks: int = Query(default=12, ge=1, le=260),
    archive_id: UUID | None = Query(default=None),
    actor: Account = Depends(current_account),
    session: AsyncSession = Depends(session_scope),
) -> list[SmoochWeekSummary]:
    """Return active or owner-authorized former-couple weekly history."""

    if archive_id is None:
        member = await active_member(session, actor.id)
    else:
        archived_member = await session.scalar(
            select(CoupleMember).where(
                CoupleMember.couple_id == archive_id,
                CoupleMember.account_id == actor.id,
                CoupleMember.left_at.is_not(None),
            )
        )
        if archived_member is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "History is unavailable")
        member = archived_member
    couple = await session.get(Couple, member.couple_id)
    if couple is None:
        if archive_id is None:
            raise relationship_inactive_error()
        raise HTTPException(status.HTTP_404_NOT_FOUND, "History is unavailable")
    if archive_id is None and couple.ended_at is not None:
        raise relationship_inactive_error()
    current = week_start(SystemClock().now(), couple.home_timezone)
    first = current - timedelta(weeks=weeks - 1)
    range_start, _ = week_bounds_utc(first, couple.home_timezone)
    _, range_end = week_bounds_utc(current, couple.home_timezone)
    rows = list(
        await session.scalars(
            select(Smooch).where(
                Smooch.couple_id == couple.id,
                Smooch.sent_at >= range_start,
                Smooch.sent_at < range_end,
            )
        )
    )
    return [
        _week_summary(rows, member.account_id, first + timedelta(weeks=index), couple.home_timezone)
        for index in range(weeks)
    ]


def _week_summary(
    rows: list[Smooch], actor_id: UUID, start: date, timezone_name: str
) -> SmoochWeekSummary:
    lower, upper = week_bounds_utc(start, timezone_name)
    selected = [item for item in rows if lower <= item.sent_at < upper]
    counts = dict.fromkeys(EMOJIS, 0)
    for item in selected:
        counts[item.emoji] += 1
    return SmoochWeekSummary(
        week_start=start,
        week_end=start + timedelta(days=6),
        sent=sum(item.sender_id == actor_id for item in selected),
        received=sum(item.recipient_id == actor_id for item in selected),
        combined=len(selected),
        emoji_counts={key: value for key, value in counts.items() if value},
    )
