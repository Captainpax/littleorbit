"""Shared countdown CRUD with optimistic revisions and retry-safe operation IDs."""

from uuid import UUID
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..activity_service import record_activity
from ..clock import SystemClock
from ..couple_access import active_member, lock_couple
from ..database import session_scope
from ..dependencies import current_account
from ..models import Account, Countdown, CountdownOperation
from ..schemas import (
    CountdownDeleteRequest,
    CountdownMutation,
    CountdownResponse,
    PublicMessage,
)

router = APIRouter(prefix="/v1/countdowns", tags=["countdowns"])


def _response(countdown: Countdown) -> CountdownResponse:
    return CountdownResponse(
        id=countdown.id,
        title=countdown.title,
        occurs_at=countdown.occurs_at,
        timezone=countdown.timezone,
        notes=countdown.notes,
        revision=countdown.revision,
        updated_at=countdown.updated_at,
    )


def _validate_time(payload: CountdownMutation) -> None:
    if payload.occurs_at.tzinfo is None:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "occurs_at needs an offset")
    try:
        ZoneInfo(payload.timezone)
    except ZoneInfoNotFoundError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Unknown IANA timezone") from exc


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


@router.get("", response_model=list[CountdownResponse])
async def list_countdowns(
    actor: Account = Depends(current_account),
    session: AsyncSession = Depends(session_scope),
) -> list[CountdownResponse]:
    """List the active couple's countdowns in event order."""

    member = await active_member(session, actor.id)
    records = list(
        await session.scalars(
            select(Countdown)
            .where(Countdown.couple_id == member.couple_id, Countdown.deleted_at.is_(None))
            .order_by(Countdown.occurs_at, Countdown.id)
        )
    )
    return [_response(item) for item in records]


@router.post("", response_model=CountdownResponse, status_code=status.HTTP_201_CREATED)
async def create_countdown(
    payload: CountdownMutation,
    actor: Account = Depends(current_account),
    session: AsyncSession = Depends(session_scope),
) -> CountdownResponse:
    """Create once even when an offline client retries the same operation."""

    _validate_time(payload)
    member = await active_member(session, actor.id)
    await lock_couple(session, member.couple_id)
    prior = await _prior_result(session, member.couple_id, payload.operation_id)
    if prior is not None:
        return _response(prior)
    now = SystemClock().now()
    countdown = Countdown(
        couple_id=member.couple_id,
        created_by=actor.id,
        title=payload.title,
        occurs_at=payload.occurs_at,
        timezone=payload.timezone,
        notes=payload.notes,
        revision=0,
        created_at=now,
        updated_at=now,
    )
    session.add(countdown)
    await session.flush()
    _record_operation(session, member.couple_id, payload.operation_id, countdown)
    await record_activity(
        session, member.couple_id, actor.id, "countdown_created",
        f"countdown:create:{payload.operation_id}", target_type="countdown",
        target_id=countdown.id, target_title=countdown.title,
    )
    await session.commit()
    return _response(countdown)


@router.put("/{countdown_id}", response_model=CountdownResponse)
async def update_countdown(
    countdown_id: UUID,
    payload: CountdownMutation,
    actor: Account = Depends(current_account),
    session: AsyncSession = Depends(session_scope),
) -> CountdownResponse:
    """Update from an expected revision or return a conflict for explicit reconciliation."""

    _validate_time(payload)
    member = await active_member(session, actor.id)
    await lock_couple(session, member.couple_id)
    prior = await _prior_result(session, member.couple_id, payload.operation_id)
    if prior is not None:
        return _response(prior)
    countdown = await session.scalar(
        select(Countdown)
        .where(
            Countdown.id == countdown_id,
            Countdown.couple_id == member.couple_id,
            Countdown.deleted_at.is_(None),
        )
        .with_for_update()
    )
    if countdown is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Countdown is unavailable")
    if payload.expected_revision is None or payload.expected_revision != countdown.revision:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            detail={"message": "Countdown changed", "current": _response(countdown).model_dump(mode="json")},
        )
    countdown.title = payload.title
    countdown.occurs_at = payload.occurs_at
    countdown.timezone = payload.timezone
    countdown.notes = payload.notes
    countdown.revision += 1
    countdown.updated_at = SystemClock().now()
    _record_operation(session, member.couple_id, payload.operation_id, countdown)
    await record_activity(
        session, member.couple_id, actor.id, "countdown_updated",
        f"countdown:update:{payload.operation_id}", target_type="countdown",
        target_id=countdown.id, target_title=countdown.title,
    )
    await session.commit()
    return _response(countdown)


@router.delete("/{countdown_id}", response_model=PublicMessage)
async def delete_countdown(
    countdown_id: UUID,
    payload: CountdownDeleteRequest,
    actor: Account = Depends(current_account),
    session: AsyncSession = Depends(session_scope),
) -> PublicMessage:
    """Soft-delete a countdown with the same offline retry and revision rules."""

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
