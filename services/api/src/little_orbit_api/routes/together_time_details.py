"""Coordinate-free day details and opt-in collection diagnostics."""

from datetime import date, datetime, timedelta
from typing import Annotated, Literal, cast
from uuid import UUID

from fastapi import APIRouter, Depends, Path, status
from sqlalchemy import delete, func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from ..clock import SystemClock
from ..couple_access import active_member, relationship_inactive_error
from ..database import session_scope
from ..dependencies import current_account
from ..models import Account, Couple, LocationSample, TogetherBucket
from ..together_history_service import day_bounds
from ..together_models import TogetherDeviceHealth
from ..together_schemas import (
    TogetherDayDetails,
    TogetherDaySegment,
    TogetherDeviceHealthResponse,
    TogetherDeviceHealthUpdate,
    TogetherDeviceHealthView,
)

router = APIRouter(prefix="/v3/together-time", tags=["together-time-v3"])


@router.get("/days/{target_day}", response_model=TogetherDayDetails)
async def together_day_details(
    target_day: date,
    actor: Account = Depends(current_account),
    session: AsyncSession = Depends(session_scope),
) -> TogetherDayDetails:
    """Return a coordinate-free local-day timeline for the active relationship."""

    member = await active_member(session, actor.id)
    couple = await _active_couple(session, member.couple_id)
    start, end = day_bounds(target_day, couple.home_timezone)
    buckets = list(
        await session.scalars(
            select(TogetherBucket)
            .where(
                TogetherBucket.couple_id == couple.id,
                TogetherBucket.bucket_start >= start,
                TogetherBucket.bucket_start < end,
            )
            .order_by(TogetherBucket.bucket_start)
        )
    )
    return TogetherDayDetails(
        day=target_day,
        timezone=couple.home_timezone,
        day_length_seconds=int((end - start).total_seconds()),
        segments=[_segment(item) for item in buckets],
    )


@router.put(
    "/device-health/{installation_id}",
    response_model=TogetherDeviceHealthView,
)
async def update_device_health(
    installation_id: Annotated[UUID, Path()],
    payload: TogetherDeviceHealthUpdate,
    actor: Account = Depends(current_account),
    session: AsyncSession = Depends(session_scope),
) -> TogetherDeviceHealthView:
    """Create or replace this installation's explicitly opted-in snapshot."""

    member = await active_member(session, actor.id)
    couple = await _active_couple(session, member.couple_id)
    now = SystemClock().now()
    values = payload.model_dump() | {
        "couple_id": couple.id,
        "account_id": actor.id,
        "installation_id": installation_id,
        "updated_at": now,
        "expires_at": now + timedelta(hours=24),
    }
    await session.execute(
        insert(TogetherDeviceHealth)
        .values(**values)
        .on_conflict_do_update(
            index_elements=["couple_id", "account_id", "installation_id"],
            set_=values,
        )
    )
    await session.commit()
    return _health_view(payload, now, await _last_location(session, couple.id, actor.id))


@router.get("/device-health", response_model=TogetherDeviceHealthResponse)
async def read_device_health(
    actor: Account = Depends(current_account),
    session: AsyncSession = Depends(session_scope),
) -> TogetherDeviceHealthResponse:
    """Return only current, opted-in snapshots for the current couple."""

    member = await active_member(session, actor.id)
    couple = await _active_couple(session, member.couple_id)
    now = SystemClock().now()
    rows = list(
        await session.scalars(
            select(TogetherDeviceHealth)
            .where(
                TogetherDeviceHealth.couple_id == couple.id,
                TogetherDeviceHealth.expires_at > now,
            )
            .order_by(TogetherDeviceHealth.updated_at.desc())
        )
    )
    last_locations = await _last_locations(session, couple.id)
    mine = [_stored_health(row, last_locations.get(row.account_id)) for row in rows]
    return TogetherDeviceHealthResponse(
        mine=[view for row, view in zip(rows, mine, strict=True) if row.account_id == actor.id],
        partner=[
            view for row, view in zip(rows, mine, strict=True) if row.account_id != actor.id
        ],
    )


@router.delete("/device-health/{installation_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_device_health(
    installation_id: Annotated[UUID, Path()],
    actor: Account = Depends(current_account),
    session: AsyncSession = Depends(session_scope),
) -> None:
    """Withdraw one installation's diagnostic sharing immediately."""

    member = await active_member(session, actor.id)
    await session.execute(
        delete(TogetherDeviceHealth).where(
            TogetherDeviceHealth.couple_id == member.couple_id,
            TogetherDeviceHealth.account_id == actor.id,
            TogetherDeviceHealth.installation_id == installation_id,
        )
    )
    await session.commit()


async def _active_couple(session: AsyncSession, couple_id: UUID) -> Couple:
    couple = await session.get(Couple, couple_id)
    if couple is None or couple.ended_at is not None:
        raise relationship_inactive_error()
    return couple


def _segment(item: TogetherBucket) -> TogetherDaySegment:
    return TogetherDaySegment(
        starts_at=item.bucket_start,
        ends_at=item.bucket_start + timedelta(minutes=1),
        evidence_state=cast(
            Literal[
                "observed",
                "bridged",
                "mixed",
                "unverified",
                "apart",
                "poor_accuracy",
            ],
            item.evidence_kind,
        ),
        observed_seconds=item.observed_seconds,
        bridged_seconds=item.bridged_seconds,
        unverified_seconds=item.unverified_seconds,
        apart_seconds=item.apart_seconds,
        poor_accuracy_seconds=item.poor_accuracy_seconds,
    )


async def _last_locations(
    session: AsyncSession, couple_id: UUID
) -> dict[UUID, datetime]:
    rows = await session.execute(
        select(LocationSample.account_id, func.max(LocationSample.recorded_at))
        .where(LocationSample.couple_id == couple_id)
        .group_by(LocationSample.account_id)
    )
    return {
        cast(UUID, account_id): cast(datetime, recorded_at)
        for account_id, recorded_at in rows.tuples().all()
    }


async def _last_location(
    session: AsyncSession, couple_id: UUID, account_id: UUID
) -> datetime | None:
    return await session.scalar(
        select(func.max(LocationSample.recorded_at)).where(
            LocationSample.couple_id == couple_id,
            LocationSample.account_id == account_id,
        )
    )


def _stored_health(
    row: TogetherDeviceHealth, last_location: datetime | None
) -> TogetherDeviceHealthView:
    payload = TogetherDeviceHealthUpdate.model_validate(
        {key: getattr(row, key) for key in TogetherDeviceHealthUpdate.model_fields}
    )
    return _health_view(payload, row.updated_at, last_location)


def _health_view(
    payload: TogetherDeviceHealthUpdate,
    updated_at: datetime,
    last_location: datetime | None,
) -> TogetherDeviceHealthView:
    return TogetherDeviceHealthView.model_validate(
        payload.model_dump()
        | {"updated_at": updated_at, "last_location_at": last_location}
    )
