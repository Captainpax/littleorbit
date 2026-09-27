"""Version 3 chronological together-time routes."""

from collections.abc import Mapping
from datetime import UTC, date, datetime, timedelta
from typing import Annotated, Literal, cast
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..clock import SystemClock
from ..couple_access import active_member, both_members_consent, relationship_inactive_error
from ..database import session_scope
from ..dependencies import current_account
from ..domain.location import RECOMPUTE_HORIZON, LiveProjection, raw_location_expires_at
from ..models import (
    Account,
    Couple,
    CoupleMember,
    LocationSample,
    TogetherBucket,
)
from ..notification_service import enqueue_together_correction_event
from ..relationship_name_service import visible_relationship_names
from ..schemas import (
    LocationBatchRequest,
    LocationBatchV2Response,
    LocationSampleRequest,
    TogetherDayCorrectionRequest,
    TogetherHistoryDay,
    TogetherSummaryV3,
)
from ..together_history_service import (
    DayBreakdown,
    day_bounds,
    day_breakdown,
    timezone_or_utc,
)
from ..together_models import TogetherDay
from ..together_time_service import (
    ALGORITHM_VERSION,
    current_live_projection,
    recompute_recent_proximity,
)

v3_router = APIRouter(prefix="/v3/together-time", tags=["together-time-v3"])


async def _locked_couple(session: AsyncSession, couple_id: UUID) -> Couple:
    couple = await session.get(
        Couple,
        couple_id,
        with_for_update=True,
        populate_existing=True,
    )
    if couple is None or couple.ended_at is not None:
        raise relationship_inactive_error()
    return couple


@v3_router.get("", response_model=TogetherSummaryV3)
async def together_summary_v3(
    actor: Account = Depends(current_account),
    session: AsyncSession = Depends(session_scope),
) -> TogetherSummaryV3:
    """Return pair age from the immutable pairing instant plus the nearby estimate."""

    member = await active_member(session, actor.id)
    couple = await session.get(Couple, member.couple_id)
    if couple is None or couple.ended_at is not None:
        raise relationship_inactive_error()
    observed = await _observed_seconds(session, couple.id)
    now = SystemClock().now()
    mutual = await both_members_consent(session, couple.id, "location_enabled")
    member_ids = await _active_member_ids(session, couple.id)
    projection = await current_live_projection(
        session, couple, member_ids, sharing_enabled=mutual, now=now
    )
    includes_legacy = await _includes_legacy_estimates(session, couple.id)
    paired_days = max(0, (now - couple.created_at).days)
    return TogetherSummaryV3(
        relationship_id=couple.id,
        home_timezone=couple.home_timezone,
        paired_at=couple.created_at,
        paired_days=paired_days,
        nearby_observed_seconds=observed,
        nearby_estimated_seconds=observed + projection.provisional_seconds,
        nearby_provisional_seconds=projection.provisional_seconds,
        server_now=now,
        counting_state=projection.state,
        counting_anchor_at=projection.anchor_at,
        counting_live_until=projection.live_until,
        nearby_last_processed_at=projection.mutual_evidence_at,
        nearby_confidence=_confidence(projection, now),
        algorithm_version=ALGORITHM_VERSION,
        includes_legacy_estimates=includes_legacy,
        proximity_threshold_m=couple.proximity_threshold_m,
        location_enabled_by_me=member.location_enabled,
        location_enabled_by_both=mutual,
        label="estimate",
    )


async def _observed_seconds(session: AsyncSession, couple_id: UUID) -> int:
    """Return the durable corrected-or-estimated total for one couple."""

    value = await session.scalar(
        select(
            func.coalesce(
                func.sum(
                    func.coalesce(
                        TogetherDay.corrected_seconds, TogetherDay.estimated_seconds
                    )
                ),
                0,
            )
        ).where(TogetherDay.couple_id == couple_id)
    )
    return int(value or 0)


async def _active_member_ids(session: AsyncSession, couple_id: UUID) -> list[UUID]:
    """Return active member IDs in the lock order shared by location workflows."""

    return list(
        await session.scalars(
            select(CoupleMember.account_id)
            .where(CoupleMember.couple_id == couple_id, CoupleMember.left_at.is_(None))
            .order_by(CoupleMember.account_id)
        )
    )


async def _includes_legacy_estimates(session: AsyncSession, couple_id: UUID) -> bool:
    """Report whether uncorrected durable totals include pre-v3 estimates."""

    value = await session.scalar(
        select(func.count())
        .select_from(TogetherDay)
        .where(
            TogetherDay.couple_id == couple_id,
            TogetherDay.corrected_seconds.is_(None),
            TogetherDay.estimate_method.in_(("legacy_v2", "mixed")),
        )
    )
    return bool(value)


@v3_router.get("/history", response_model=list[TogetherHistoryDay])
async def together_history(
    days: Annotated[int, Query(ge=1, le=30)] = 30,
    actor: Account = Depends(current_account),
    session: AsyncSession = Depends(session_scope),
) -> list[TogetherHistoryDay]:
    """Return up to thirty shared-home calendar days without coordinates."""

    member = await active_member(session, actor.id)
    couple = await _locked_couple(session, member.couple_id)
    today = SystemClock().now().astimezone(timezone_or_utc(couple.home_timezone)).date()
    cutoff = today - timedelta(days=days - 1)
    records = list(
        await session.scalars(
            select(TogetherDay).where(
                TogetherDay.couple_id == member.couple_id,
                TogetherDay.day >= cutoff,
            )
        )
    )
    corrector_ids = {item.corrected_by for item in records if item.corrected_by}
    visible_names = await visible_relationship_names(
        session, couple.id, corrector_ids, actor.id
    )
    names = {account_id: item.display_name for account_id, item in visible_names.items()}
    by_day = {item.day: item for item in records}
    breakdowns = {
        target: await day_breakdown(session, couple.id, target, couple.home_timezone)
        for target in (today - timedelta(days=offset) for offset in range(days))
    }
    return [
        _history_response(
            today - timedelta(days=offset),
            by_day,
            names,
            breakdowns[today - timedelta(days=offset)],
            couple.home_timezone,
        )
        for offset in range(days - 1, -1, -1)
    ]


def _history_response(
    day: date,
    records: dict[date, TogetherDay],
    names: Mapping[UUID, str | None],
    breakdown: DayBreakdown,
    timezone_name: str,
) -> TogetherHistoryDay:
    start, end = day_bounds(day, timezone_name)
    day_length = int((end - start).total_seconds())
    item = records.get(day)
    if item is None:
        return TogetherHistoryDay(
            day=day,
            estimated_seconds=0,
            corrected=False,
            estimate_method="current_v4",
            day_timezone=timezone_name,
            day_length_seconds=day_length,
            observed_seconds=breakdown.observed,
            bridged_seconds=breakdown.bridged,
            unverified_seconds=breakdown.unverified,
            apart_seconds=breakdown.apart,
            poor_accuracy_seconds=breakdown.poor_accuracy,
        )
    method = cast(
        Literal["legacy_v2", "mixed", "current_v3", "current_v4", "corrected"],
        "corrected" if item.corrected_seconds is not None else item.estimate_method,
    )
    return TogetherHistoryDay(
        day=day,
        estimated_seconds=item.effective_seconds,
        corrected=item.corrected_seconds is not None,
        estimate_method=method,
        revision=item.revision,
        corrected_by_display_name=names.get(item.corrected_by) if item.corrected_by else None,
        correction_reason=item.correction_reason,
        day_timezone=timezone_name,
        day_length_seconds=day_length,
        observed_seconds=breakdown.observed,
        bridged_seconds=breakdown.bridged,
        unverified_seconds=breakdown.unverified,
        apart_seconds=breakdown.apart,
        poor_accuracy_seconds=breakdown.poor_accuracy,
    )


def _confidence(
    projection: LiveProjection, now: datetime
) -> Literal["unavailable", "low", "medium", "high"]:
    if projection.mutual_evidence_at is None:
        return "unavailable"
    age = now - projection.mutual_evidence_at
    if projection.state == "nearby" and age <= timedelta(minutes=2):
        return "high"
    if age <= timedelta(minutes=5):
        return "medium"
    return "low" if age <= timedelta(hours=24) else "unavailable"


@v3_router.put("/days/{target_day}", response_model=TogetherHistoryDay)
async def correct_together_day(
    target_day: date,
    payload: TogetherDayCorrectionRequest,
    request: Request,
    actor: Account = Depends(current_account),
    session: AsyncSession = Depends(session_scope),
) -> TogetherHistoryDay:
    """Apply an optimistic correction to one completed local day and notify the partner."""

    member = await active_member(session, actor.id)
    couple = await _locked_couple(session, member.couple_id)
    timezone = timezone_or_utc(couple.home_timezone)
    today = SystemClock().now().astimezone(timezone).date()
    if target_day >= today or target_day < couple.created_at.astimezone(timezone).date():
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Choose a completed paired day")
    start, end = day_bounds(target_day, couple.home_timezone)
    if payload.estimated_seconds > int((end - start).total_seconds()):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Time exceeds this local day")
    item = await _correctable_day(session, couple, target_day)
    if item.revision != payload.expected_revision:
        raise HTTPException(status.HTTP_409_CONFLICT, "Together-time day changed; refresh")
    now = SystemClock().now()
    item.corrected_seconds = payload.estimated_seconds
    item.correction_reason = payload.reason
    item.corrected_by = actor.id
    item.corrected_at = now
    item.updated_at = now
    item.revision += 1
    recipient = await enqueue_together_correction_event(
        session, couple.id, actor.id, item.id, target_day, item.revision
    )
    await session.commit()
    if recipient is not None:
        await request.app.state.notification_connections.available(recipient)
    return await _corrected_response(session, couple, actor, item, target_day, start, end)


async def _correctable_day(
    session: AsyncSession, couple: Couple, target_day: date
) -> TogetherDay:
    item = await session.scalar(
        select(TogetherDay)
        .where(TogetherDay.couple_id == couple.id, TogetherDay.day == target_day)
        .with_for_update()
    )
    if item is None:
        item = TogetherDay(
            couple_id=couple.id,
            day=target_day,
            day_timezone=couple.home_timezone,
            estimated_seconds=await _bucket_total(
                session, couple.id, target_day, couple.home_timezone
            ),
            estimate_method="current_v4",
            revision=0,
            updated_at=SystemClock().now(),
        )
        session.add(item)
        await session.flush()
    return item


async def _corrected_response(
    session: AsyncSession,
    couple: Couple,
    actor: Account,
    item: TogetherDay,
    target_day: date,
    start: datetime,
    end: datetime,
) -> TogetherHistoryDay:
    names = await visible_relationship_names(session, couple.id, (actor.id,), actor.id)
    return TogetherHistoryDay(
        day=target_day,
        day_timezone=couple.home_timezone,
        day_length_seconds=int((end - start).total_seconds()),
        estimated_seconds=item.effective_seconds,
        corrected=True,
        estimate_method="corrected",
        revision=item.revision,
        corrected_by_display_name=names[actor.id].display_name,
        correction_reason=item.correction_reason,
        **_breakdown_fields(
            await day_breakdown(session, couple.id, target_day, couple.home_timezone)
        ),
    )


async def _bucket_total(
    session: AsyncSession, couple_id: UUID, target_day: date, timezone_name: str
) -> int:
    start, end = day_bounds(target_day, timezone_name)
    value = await session.scalar(
        select(func.coalesce(func.sum(TogetherBucket.duration_seconds), 0)).where(
            TogetherBucket.couple_id == couple_id,
            TogetherBucket.bucket_start >= start,
            TogetherBucket.bucket_start < end,
        )
    )
    return min(int(value or 0), int((end - start).total_seconds()))


def _breakdown_fields(breakdown: DayBreakdown) -> dict[str, int]:
    return {
        "observed_seconds": breakdown.observed,
        "bridged_seconds": breakdown.bridged,
        "unverified_seconds": breakdown.unverified,
        "apart_seconds": breakdown.apart,
        "poor_accuracy_seconds": breakdown.poor_accuracy,
    }


@v3_router.post("/location-batches", response_model=LocationBatchV2Response)
async def upload_locations_v2(
    payload: LocationBatchRequest,
    actor: Account = Depends(current_account),
    session: AsyncSession = Depends(session_scope),
) -> LocationBatchV2Response:
    """Store a bounded retry-safe batch only while both partners consent."""

    member = await active_member(session, actor.id)
    couple = await _locked_couple(session, member.couple_id)
    if payload.relationship_id != couple.id:
        raise relationship_inactive_error()
    if not await both_members_consent(session, couple.id, "location_enabled"):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Mutual location sharing is disabled")
    now = SystemClock().now()
    accepted, duplicates, changed_at = await _store_location_batch(
        session, actor.id, couple.id, payload.samples, now
    )
    await session.flush()
    member_ids = await _active_member_ids(session, couple.id)
    seconds = await recompute_recent_proximity(
        session, couple, member_ids, changed_at, now
    )
    await session.commit()
    return LocationBatchV2Response(
        accepted=accepted,
        duplicates=duplicates,
        nearby_seconds_recomputed=seconds,
    )


async def _store_location_batch(
    session: AsyncSession,
    account_id: UUID,
    couple_id: UUID,
    samples: list[LocationSampleRequest],
    now: datetime,
) -> tuple[int, int, list[datetime]]:
    """Store new samples and classify exact retry-safe duplicates."""

    accepted = 0
    duplicates = 0
    changed_at: list[datetime] = []
    for sample in samples:
        recorded_at = await _store_location_sample(
            session, account_id, couple_id, sample, now
        )
        if recorded_at is None:
            duplicates += 1
        else:
            accepted += 1
            changed_at.append(recorded_at)
    return accepted, duplicates, changed_at


async def _store_location_sample(
    session: AsyncSession,
    account_id: UUID,
    couple_id: UUID,
    sample: LocationSampleRequest,
    now: datetime,
) -> datetime | None:
    """Store one sample or return None for an exact idempotent replay."""

    _validate_sample_time(sample.recorded_at, now)
    existing = await session.scalar(
        select(LocationSample).where(
            LocationSample.account_id == account_id,
            LocationSample.sample_id == sample.sample_id,
        )
    )
    if existing is not None:
        if not _same_sample(existing, couple_id, sample):
            raise HTTPException(
                status.HTTP_409_CONFLICT,
                {"code": "sample_id_conflict", "message": "Sample identity changed"},
            )
        return None
    recorded_at = sample.recorded_at.astimezone(UTC)
    session.add(
        LocationSample(
            sample_id=sample.sample_id,
            account_id=account_id,
            couple_id=couple_id,
            recorded_at=recorded_at,
            latitude=sample.latitude,
            longitude=sample.longitude,
            accuracy_m=sample.accuracy_m,
            expires_at=raw_location_expires_at(recorded_at),
        )
    )
    return recorded_at


def _validate_sample_time(recorded_at: datetime, now: datetime) -> None:
    if recorded_at.tzinfo is None:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "recorded_at needs an offset")
    instant = recorded_at.astimezone(UTC)
    if instant < now - RECOMPUTE_HORIZON or instant > now + timedelta(minutes=5):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "sample time is outside policy")


def _same_sample(
    stored: LocationSample, couple_id: UUID, incoming: LocationSampleRequest
) -> bool:
    """Compare an idempotent replay without logging or returning coordinate values."""

    return bool(
        stored.couple_id == couple_id
        and stored.recorded_at == incoming.recorded_at.astimezone(UTC)
        and stored.latitude == incoming.latitude
        and stored.longitude == incoming.longitude
        and stored.accuracy_m == incoming.accuracy_m
    )
