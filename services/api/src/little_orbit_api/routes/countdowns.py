"""Shared countdowns with calendar-aware timing and private reminder choices."""

from datetime import UTC, datetime, time
from typing import Literal, cast
from uuid import UUID
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..activity_service import record_activity
from ..clock import SystemClock
from ..countdown_models import Countdown, CountdownOperation, CountdownReminder
from ..couple_access import active_member, lock_couple
from ..database import session_scope
from ..dependencies import current_account
from ..models import Account
from ..notification_service import enqueue_countdown_event
from ..schemas import (
    CountdownDeleteRequest,
    CountdownMutation,
    CountdownReminderUpdate,
    CountdownResponse,
    PublicMessage,
)

router = APIRouter(prefix="/v1/countdowns", tags=["countdowns"])


def _validated_time(payload: CountdownMutation) -> datetime:
    if payload.occurs_at.tzinfo is None:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "occurs_at needs an offset")
    try:
        zone = ZoneInfo(payload.timezone)
    except ZoneInfoNotFoundError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Unknown IANA timezone") from exc
    if payload.timing_kind == "all_day":
        if payload.occurs_on is None:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "occurs_on is required")
        return datetime.combine(payload.occurs_on, time.min, zone).astimezone(UTC)
    if payload.occurs_on is not None:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY, "occurs_on is only for all-day events"
        )
    return payload.occurs_at.astimezone(UTC)


async def _reminders(session: AsyncSession, countdown_id: UUID, account_id: UUID) -> list[int]:
    return list(
        await session.scalars(
            select(CountdownReminder.offset_minutes)
            .where(
                CountdownReminder.countdown_id == countdown_id,
                CountdownReminder.account_id == account_id,
            )
            .order_by(CountdownReminder.offset_minutes)
        )
    )


async def _response(
    session: AsyncSession, countdown: Countdown, account_id: UUID
) -> CountdownResponse:
    return CountdownResponse(
        id=countdown.id,
        title=countdown.title,
        occurs_at=countdown.occurs_at,
        timezone=countdown.timezone,
        timing_kind=cast(Literal["timed", "all_day"], countdown.timing_kind),
        occurs_on=countdown.occurs_on,
        my_reminder_offsets_minutes=await _reminders(session, countdown.id, account_id),
        notes=countdown.notes,
        revision=countdown.revision,
        updated_at=countdown.updated_at,
    )


async def _prior_result(
    session: AsyncSession, couple_id: UUID, operation_id: UUID
) -> Countdown | None:
    countdown_id = await session.scalar(
        select(CountdownOperation.countdown_id).where(
            CountdownOperation.couple_id == couple_id,
            CountdownOperation.operation_id == operation_id,
        )
    )
    return await session.get(Countdown, countdown_id) if countdown_id else None


def _record_operation(
    session: AsyncSession, couple_id: UUID, operation_id: UUID, countdown: Countdown
) -> None:
    session.add(
        CountdownOperation(
            couple_id=couple_id,
            operation_id=operation_id,
            countdown_id=countdown.id,
            resulting_revision=countdown.revision,
            applied_at=SystemClock().now(),
        )
    )


async def _notify(request: Request, recipient_id: UUID | None) -> None:
    if recipient_id is not None:
        await request.app.state.notification_connections.available(recipient_id)


@router.get("", response_model=list[CountdownResponse])
async def list_countdowns(
    actor: Account = Depends(current_account),
    session: AsyncSession = Depends(session_scope),
) -> list[CountdownResponse]:
    """List upcoming and past countdowns; neither is silently discarded."""

    member = await active_member(session, actor.id)
    records = list(
        await session.scalars(
            select(Countdown)
            .where(Countdown.couple_id == member.couple_id, Countdown.deleted_at.is_(None))
            .order_by(Countdown.occurs_at, Countdown.id)
        )
    )
    return [await _response(session, item, actor.id) for item in records]


@router.post("", response_model=CountdownResponse, status_code=status.HTTP_201_CREATED)
async def create_countdown(
    payload: CountdownMutation,
    request: Request,
    actor: Account = Depends(current_account),
    session: AsyncSession = Depends(session_scope),
) -> CountdownResponse:
    """Create once and notify the partner from the accepted transaction."""

    occurs_at = _validated_time(payload)
    member = await active_member(session, actor.id)
    await lock_couple(session, member.couple_id)
    prior = await _prior_result(session, member.couple_id, payload.operation_id)
    if prior is not None:
        return await _response(session, prior, actor.id)
    now = SystemClock().now()
    countdown = Countdown(
        couple_id=member.couple_id,
        created_by=actor.id,
        title=payload.title,
        occurs_at=occurs_at,
        timezone=payload.timezone,
        timing_kind=payload.timing_kind,
        occurs_on=payload.occurs_on,
        notes=payload.notes,
        revision=0,
        created_at=now,
        updated_at=now,
    )
    session.add(countdown)
    await session.flush()
    _record_operation(session, member.couple_id, payload.operation_id, countdown)
    await record_activity(
        session,
        member.couple_id,
        actor.id,
        "countdown_created",
        f"countdown:create:{payload.operation_id}",
        target_type="countdown",
        target_id=countdown.id,
        target_title=countdown.title,
    )
    recipient = await enqueue_countdown_event(
        session, countdown, actor.id, "countdown_created", payload.operation_id
    )
    await session.commit()
    await _notify(request, recipient)
    return await _response(session, countdown, actor.id)


@router.put("/{countdown_id}", response_model=CountdownResponse)
async def update_countdown(
    countdown_id: UUID,
    payload: CountdownMutation,
    request: Request,
    actor: Account = Depends(current_account),
    session: AsyncSession = Depends(session_scope),
) -> CountdownResponse:
    """Update optimistically and alert only when the shared timing changed."""

    occurs_at = _validated_time(payload)
    member = await active_member(session, actor.id)
    await lock_couple(session, member.couple_id)
    prior = await _prior_result(session, member.couple_id, payload.operation_id)
    if prior is not None:
        return await _response(session, prior, actor.id)
    countdown = await _locked_countdown(session, member.couple_id, countdown_id)
    if payload.expected_revision is None or payload.expected_revision != countdown.revision:
        current = await _response(session, countdown, actor.id)
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            detail={"message": "Countdown changed", "current": current.model_dump(mode="json")},
        )
    timing_changed = _timing_changed(countdown, payload, occurs_at)
    _apply_update(countdown, payload, occurs_at)
    _record_operation(session, member.couple_id, payload.operation_id, countdown)
    await record_activity(
        session,
        member.couple_id,
        actor.id,
        "countdown_updated",
        f"countdown:update:{payload.operation_id}",
        target_type="countdown",
        target_id=countdown.id,
        target_title=countdown.title,
    )
    recipient = None
    if timing_changed:
        recipient = await enqueue_countdown_event(
            session, countdown, actor.id, "countdown_rescheduled", payload.operation_id
        )
    await session.commit()
    await _notify(request, recipient)
    return await _response(session, countdown, actor.id)


async def _locked_countdown(
    session: AsyncSession, couple_id: UUID, countdown_id: UUID
) -> Countdown:
    countdown = await session.scalar(
        select(Countdown)
        .where(
            Countdown.id == countdown_id,
            Countdown.couple_id == couple_id,
            Countdown.deleted_at.is_(None),
        )
        .with_for_update()
    )
    if countdown is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Countdown is unavailable")
    return countdown


def _timing_changed(countdown: Countdown, payload: CountdownMutation, occurs_at: datetime) -> bool:
    return (
        countdown.occurs_at != occurs_at
        or countdown.timezone != payload.timezone
        or countdown.timing_kind != payload.timing_kind
        or countdown.occurs_on != payload.occurs_on
    )


def _apply_update(countdown: Countdown, payload: CountdownMutation, occurs_at: datetime) -> None:
    countdown.title = payload.title
    countdown.occurs_at = occurs_at
    countdown.timezone = payload.timezone
    countdown.timing_kind = payload.timing_kind
    countdown.occurs_on = payload.occurs_on
    countdown.notes = payload.notes
    countdown.revision += 1
    countdown.updated_at = SystemClock().now()


@router.put("/{countdown_id}/reminders", response_model=CountdownResponse)
async def replace_reminders(
    countdown_id: UUID,
    payload: CountdownReminderUpdate,
    actor: Account = Depends(current_account),
    session: AsyncSession = Depends(session_scope),
) -> CountdownResponse:
    """Replace only the caller's account-synced reminder offsets."""

    if len(set(payload.offsets_minutes)) != len(payload.offsets_minutes):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Reminder offsets must be unique")
    member = await active_member(session, actor.id)
    await lock_couple(session, member.couple_id)
    countdown = await _locked_countdown(session, member.couple_id, countdown_id)
    await session.execute(
        delete(CountdownReminder).where(
            CountdownReminder.countdown_id == countdown.id,
            CountdownReminder.account_id == actor.id,
        )
    )
    now = SystemClock().now()
    session.add_all(
        [
            CountdownReminder(
                countdown_id=countdown.id,
                account_id=actor.id,
                offset_minutes=offset,
                created_at=now,
            )
            for offset in sorted(payload.offsets_minutes)
        ]
    )
    await session.commit()
    return await _response(session, countdown, actor.id)


@router.delete("/{countdown_id}", response_model=PublicMessage)
async def delete_countdown(
    countdown_id: UUID,
    payload: CountdownDeleteRequest,
    actor: Account = Depends(current_account),
    session: AsyncSession = Depends(session_scope),
) -> PublicMessage:
    """Soft-delete a countdown with the same retry and revision rules."""

    member = await active_member(session, actor.id)
    await lock_couple(session, member.couple_id)
    if await _prior_result(session, member.couple_id, payload.operation_id):
        return PublicMessage(message="Countdown deleted.")
    countdown = await session.scalar(
        select(Countdown)
        .where(Countdown.id == countdown_id, Countdown.couple_id == member.couple_id)
        .with_for_update()
    )
    if countdown is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Countdown is unavailable")
    if countdown.deleted_at is None and countdown.revision != payload.expected_revision:
        raise HTTPException(status.HTTP_409_CONFLICT, "Countdown changed")
    countdown.deleted_at = countdown.deleted_at or SystemClock().now()
    countdown.updated_at = SystemClock().now()
    countdown.revision += 1
    _record_operation(session, member.couple_id, payload.operation_id, countdown)
    await session.commit()
    return PublicMessage(message="Countdown deleted.")
