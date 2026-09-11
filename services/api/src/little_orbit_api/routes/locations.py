"""Consented location ingestion and non-overlapping together-time estimates."""

from datetime import UTC, datetime, timedelta
from typing import cast
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from ..clock import SystemClock
from ..couple_access import active_member, both_members_consent
from ..database import session_scope
from ..dependencies import current_account
from ..domain.location import Point, decide_proximity
from ..models import Account, Couple, CoupleMember, LocationSample, SecurityEvent, TogetherBucket
from ..schemas import (
    LocationBatchRequest,
    LocationBatchResponse,
    LocationSampleRequest,
    TogetherBucketResponse,
    TogetherCorrectionRequest,
    TogetherSummary,
)

router = APIRouter(prefix="/v1/together-time", tags=["together-time"])


def _validate_recorded_at(recorded_at: datetime) -> None:
    now = SystemClock().now()
    if recorded_at.tzinfo is None:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "recorded_at needs an offset")
    instant = recorded_at.astimezone(UTC)
    if instant < now - timedelta(hours=24) or instant > now + timedelta(minutes=5):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "sample time is outside policy")


async def _partner_id(
    session: AsyncSession, couple_id: UUID, actor_id: UUID
) -> UUID | None:
    return cast(
        UUID | None,
        await session.scalar(
            select(CoupleMember.account_id).where(
                CoupleMember.couple_id == couple_id,
                CoupleMember.account_id != actor_id,
                CoupleMember.left_at.is_(None),
            )
        )
    )


async def _nearest_partner_sample(
    session: AsyncSession,
    couple_id: UUID,
    partner_id: UUID,
    recorded_at: datetime,
) -> LocationSample | None:
    lower = recorded_at - timedelta(minutes=5)
    upper = recorded_at + timedelta(minutes=5)
    candidates = list(
        await session.scalars(
            select(LocationSample).where(
                LocationSample.couple_id == couple_id,
                LocationSample.account_id == partner_id,
                LocationSample.recorded_at.between(lower, upper),
            )
        )
    )
    if not candidates:
        return None
    return min(
        candidates,
        key=lambda sample: abs((sample.recorded_at - recorded_at).total_seconds()),
    )


async def _count_pair(
    session: AsyncSession,
    couple: Couple,
    actor_sample: LocationSampleRequest,
    partner_sample: LocationSample,
) -> bool:
    decision = decide_proximity(
        Point(actor_sample.latitude, actor_sample.longitude, actor_sample.accuracy_m),
        Point(partner_sample.latitude, partner_sample.longitude, partner_sample.accuracy_m),
        couple.proximity_threshold_m,
    )
    if not decision.together:
        return False
    bucket_start = actor_sample.recorded_at.astimezone(UTC).replace(second=0, microsecond=0)
    statement = (
        insert(TogetherBucket)
        .values(
            couple_id=couple.id,
            bucket_start=bucket_start,
            duration_seconds=60,
            estimated_distance_m=decision.measured_distance_m,
            created_at=SystemClock().now(),
        )
        .on_conflict_do_nothing(index_elements=["couple_id", "bucket_start"])
        .returning(TogetherBucket.id)
    )
    return (await session.scalar(statement)) is not None


@router.post("/locations", response_model=LocationBatchResponse)
async def upload_locations(
    payload: LocationBatchRequest,
    actor: Account = Depends(current_account),
    session: AsyncSession = Depends(session_scope),
) -> LocationBatchResponse:
    """Deduplicate a bounded batch and derive minutes only under mutual consent."""

    member = await active_member(session, actor.id)
    if not member.location_enabled:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Location sharing is disabled")
    couple = await session.get(Couple, member.couple_id)
    if couple is None:
        raise HTTPException(status.HTTP_409_CONFLICT, "Pairing state is unavailable")
    mutual = await both_members_consent(session, member.couple_id, "location_enabled")
    partner_id = await _partner_id(session, member.couple_id, actor.id) if mutual else None
    accepted = 0
    together = 0
    for item in payload.samples:
        _validate_recorded_at(item.recorded_at)
        sample_id = await session.scalar(
            insert(LocationSample)
            .values(
                sample_id=item.sample_id,
                account_id=actor.id,
                couple_id=member.couple_id,
                recorded_at=item.recorded_at.astimezone(UTC),
                latitude=item.latitude,
                longitude=item.longitude,
                accuracy_m=item.accuracy_m,
                expires_at=SystemClock().now() + timedelta(hours=24),
            )
            .on_conflict_do_nothing(index_elements=["account_id", "sample_id"])
            .returning(LocationSample.id)
        )
        if sample_id is None:
            continue
        accepted += 1
        if partner_id is None:
            continue
        partner_sample = await _nearest_partner_sample(
            session, member.couple_id, partner_id, item.recorded_at
        )
        if partner_sample and await _count_pair(session, couple, item, partner_sample):
            together += 1
    await session.commit()
    return LocationBatchResponse(
        accepted=accepted,
        duplicates=len(payload.samples) - accepted,
        together_minutes_added=together,
    )


@router.get("", response_model=TogetherSummary)
async def together_summary(
    actor: Account = Depends(current_account),
    session: AsyncSession = Depends(session_scope),
) -> TogetherSummary:
    """Return the aggregate estimate without exposing either partner's coordinates."""

    member = await active_member(session, actor.id)
    couple = await session.get(Couple, member.couple_id)
    if couple is None:
        raise HTTPException(status.HTTP_409_CONFLICT, "Pairing state is unavailable")
    total, updated = (
        await session.execute(
            select(
                func.coalesce(func.sum(TogetherBucket.duration_seconds), 0),
                func.max(TogetherBucket.created_at),
            ).where(TogetherBucket.couple_id == member.couple_id)
        )
    ).one()
    return TogetherSummary(
        estimated_seconds=int(total),
        last_updated_at=updated,
        proximity_threshold_m=couple.proximity_threshold_m,
        label="estimate",
    )


@router.get("/buckets", response_model=list[TogetherBucketResponse])
async def together_buckets(
    actor: Account = Depends(current_account),
    session: AsyncSession = Depends(session_scope),
) -> list[TogetherBucketResponse]:
    """List recent correctable estimate buckets without returning raw coordinates."""

    member = await active_member(session, actor.id)
    records = list(
        await session.scalars(
            select(TogetherBucket)
            .where(TogetherBucket.couple_id == member.couple_id)
            .order_by(TogetherBucket.bucket_start.desc())
            .limit(500)
        )
    )
    return [
        TogetherBucketResponse(
            id=item.id,
            bucket_start=item.bucket_start,
            duration_seconds=item.duration_seconds,
            corrected_at=item.corrected_at,
        )
        for item in records
    ]


@router.patch("/buckets/{bucket_id}", response_model=TogetherSummary)
async def correct_bucket(
    bucket_id: UUID,
    payload: TogetherCorrectionRequest,
    actor: Account = Depends(current_account),
    session: AsyncSession = Depends(session_scope),
) -> TogetherSummary:
    """Apply an attributable correction without creating overlapping intervals."""

    member = await active_member(session, actor.id)
    bucket = await session.scalar(
        select(TogetherBucket)
        .where(TogetherBucket.id == bucket_id, TogetherBucket.couple_id == member.couple_id)
        .with_for_update()
    )
    if bucket is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Together-time minute is unavailable")
    now = SystemClock().now()
    bucket.duration_seconds = payload.duration_seconds
    bucket.corrected_by = actor.id
    bucket.correction_reason = payload.reason
    bucket.corrected_at = now
    session.add(
        SecurityEvent(
            actor_id=actor.id,
            event_type="together_time_correction",
            outcome="accepted",
            metadata_json={"bucket_id": str(bucket.id)},
            created_at=now,
        )
    )
    await session.commit()
    return await together_summary(actor, session)
