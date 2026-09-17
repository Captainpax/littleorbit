"""Transactional helpers for RC6 relationship dates and proximity estimates."""

from datetime import UTC, date, datetime, timedelta
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import delete, func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from .clock import SystemClock
from .domain.location import (
    MAX_MUTUAL_EVIDENCE_AGE,
    RECOMPUTE_HORIZON,
    LiveProjection,
    Point,
    TimedPoint,
    build_proximity_timeline,
    live_projection,
)
from .models import (
    Couple,
    LocationSample,
    TogetherBucket,
)
from .together_models import TogetherDay

ALGORITHM_VERSION = 3


async def recompute_recent_proximity(
    session: AsyncSession,
    couple: Couple,
    member_ids: list[UUID],
    changed_at: list[datetime],
    now: datetime | None = None,
) -> int:
    """Reconcile only raw-data ranges affected by newly accepted observations."""

    if len(member_ids) != 2:
        raise HTTPException(status.HTTP_409_CONFLICT, "Pairing state changed; retry")
    current = (now or SystemClock().now()).astimezone(UTC)
    safe_start = current - RECOMPUTE_HORIZON
    ranges = _recompute_ranges(changed_at, safe_start, current)
    if couple.proximity_algorithm_version < ALGORITHM_VERSION:
        ranges = [(safe_start, current)]
    total = 0
    affected_days: set[date] = set()
    for start, end in ranges:
        total += await _replace_range(
            session, couple, member_ids, start, end, current
        )
        affected_days.update(_days_between(start, end))
    streams = await _latest_streams(session, couple.id, member_ids, not_after=current)
    couple.proximity_processed_through = _mutual_sample_freshness(streams)
    couple.proximity_algorithm_version = ALGORITHM_VERSION
    couple.updated_at = current
    await _sync_daily_totals(session, couple.id, affected_days, current)
    return total


async def current_live_projection(
    session: AsyncSession,
    couple: Couple,
    member_ids: list[UUID],
    *,
    sharing_enabled: bool,
    now: datetime,
) -> LiveProjection:
    """Derive current display authorization from the newest two samples per member."""

    if len(member_ids) != 2:
        return live_projection(
            build_proximity_timeline([], []), now, sharing_enabled=False
        )
    streams = await _latest_streams(session, couple.id, member_ids, not_after=now)
    timeline = build_proximity_timeline(
        streams[0], streams[1], couple.proximity_threshold_m
    )
    return live_projection(timeline, now, sharing_enabled=sharing_enabled)


async def _replace_range(
    session: AsyncSession,
    couple: Couple,
    member_ids: list[UUID],
    start: datetime,
    end: datetime,
    now: datetime,
) -> int:
    """Replace uncorrected buckets in one minute-aligned impact range."""

    bucket_start = _floor_minute(start)
    bucket_end = _ceil_minute(end)
    context_start = bucket_start - MAX_MUTUAL_EVIDENCE_AGE
    context_end = min(now, bucket_end + MAX_MUTUAL_EVIDENCE_AGE)
    samples = list(
        await session.scalars(
            select(LocationSample)
            .where(
                LocationSample.couple_id == couple.id,
                LocationSample.recorded_at >= context_start,
                LocationSample.recorded_at <= context_end,
            )
            .order_by(LocationSample.recorded_at, LocationSample.sample_id)
        )
    )
    streams = [_timed_points(samples, member_id) for member_id in member_ids]
    timeline = build_proximity_timeline(
        streams[0],
        streams[1],
        couple.proximity_threshold_m,
        clip_start=bucket_start,
        clip_end=bucket_end,
    )
    await session.execute(
        delete(TogetherBucket).where(
            TogetherBucket.couple_id == couple.id,
            TogetherBucket.bucket_start >= bucket_start,
            TogetherBucket.bucket_start < bucket_end,
            TogetherBucket.corrected_at.is_(None),
        )
    )
    for item in timeline.estimates:
        await session.execute(
            insert(TogetherBucket)
            .values(
                couple_id=couple.id,
                bucket_start=item.bucket_start,
                duration_seconds=item.duration_seconds,
                estimated_distance_m=item.estimated_distance_m,
                algorithm_version=ALGORITHM_VERSION,
                created_at=now,
            )
            .on_conflict_do_nothing(index_elements=["couple_id", "bucket_start"])
        )
    return sum(item.duration_seconds for item in timeline.estimates)


def _recompute_ranges(
    changed_at: list[datetime], safe_start: datetime, now: datetime
) -> list[tuple[datetime, datetime]]:
    """Merge bounded impact windows around accepted observations."""

    raw = sorted(
        (
            max(safe_start, value.astimezone(UTC) - MAX_MUTUAL_EVIDENCE_AGE),
            min(now, value.astimezone(UTC) + MAX_MUTUAL_EVIDENCE_AGE),
        )
        for value in changed_at
        if safe_start <= value.astimezone(UTC) <= now
    )
    merged: list[tuple[datetime, datetime]] = []
    for start, end in raw:
        if end <= start:
            continue
        if merged and start <= merged[-1][1]:
            merged[-1] = (merged[-1][0], max(merged[-1][1], end))
        else:
            merged.append((start, end))
    return merged


def _mutual_sample_freshness(streams: list[list[TimedPoint]]) -> datetime | None:
    """Return the newest instant supported by a recent sample from both members."""

    if len(streams) != 2 or any(not stream for stream in streams):
        return None
    return min(stream[-1].recorded_at for stream in streams)


async def _sync_daily_totals(
    session: AsyncSession, couple_id: UUID, days: set[date], now: datetime
) -> None:
    """Refresh coordinate-free daily totals while preserving explicit corrections."""

    for current_day in sorted(days):
        start = datetime.combine(current_day, datetime.min.time(), UTC)
        end = start + timedelta(days=1)
        seconds, minimum, maximum = (
            await session.execute(
                select(
                    func.coalesce(func.sum(TogetherBucket.duration_seconds), 0),
                    func.min(TogetherBucket.algorithm_version),
                    func.max(TogetherBucket.algorithm_version),
                ).where(
                    TogetherBucket.couple_id == couple_id,
                    TogetherBucket.bucket_start >= start,
                    TogetherBucket.bucket_start < end,
                )
            )
        ).one()
        method = _estimate_method(minimum, maximum)
        await session.execute(
            insert(TogetherDay)
            .values(
                couple_id=couple_id,
                day=current_day,
                estimated_seconds=min(int(seconds), 86_400),
                estimate_method=method,
                revision=0,
                updated_at=now,
            )
            .on_conflict_do_update(
                index_elements=["couple_id", "day"],
                set_={
                    "estimated_seconds": min(int(seconds), 86_400),
                    "estimate_method": method,
                    "updated_at": now,
                },
            )
        )


def _estimate_method(minimum: int | None, maximum: int | None) -> str:
    """Describe whether one daily total contains legacy or current buckets."""

    if minimum is None or maximum is None or minimum >= ALGORITHM_VERSION:
        return "current_v3"
    return "legacy_v2" if maximum < ALGORITHM_VERSION else "mixed"


async def _latest_streams(
    session: AsyncSession,
    couple_id: UUID,
    member_ids: list[UUID],
    *,
    not_after: datetime,
) -> list[list[TimedPoint]]:
    """Load only enough retained evidence to classify and confirm current state."""

    streams: list[list[TimedPoint]] = []
    for member_id in member_ids:
        records = list(
            await session.scalars(
                select(LocationSample)
                .where(
                    LocationSample.couple_id == couple_id,
                    LocationSample.account_id == member_id,
                    LocationSample.recorded_at <= not_after,
                )
                .order_by(LocationSample.recorded_at.desc(), LocationSample.sample_id.desc())
                .limit(2)
            )
        )
        streams.append(_timed_points(list(reversed(records)), member_id))
    return streams


def _days_between(start: datetime, end: datetime) -> set[date]:
    """Return UTC days touched by one half-open impact range."""

    first = start.astimezone(UTC).date()
    last = max(start, end - timedelta(microseconds=1)).astimezone(UTC).date()
    return {first + timedelta(days=offset) for offset in range((last - first).days + 1)}


def _floor_minute(value: datetime) -> datetime:
    return value.astimezone(UTC).replace(second=0, microsecond=0)


def _ceil_minute(value: datetime) -> datetime:
    floor = _floor_minute(value)
    return floor if value == floor else floor + timedelta(minutes=1)


def _timed_points(samples: list[LocationSample], account_id: UUID) -> list[TimedPoint]:
    return [
        TimedPoint(
            sample_id=str(item.sample_id),
            recorded_at=item.recorded_at.astimezone(UTC),
            point=Point(item.latitude, item.longitude, item.accuracy_m),
        )
        for item in samples
        if item.account_id == account_id
    ]


def relationship_days(start: date | None, now: datetime | None = None) -> int | None:
    """Return complete UTC calendar days since the mutually accepted date."""

    if start is None:
        return None
    today = (now or SystemClock().now()).astimezone(UTC).date()
    return max(0, (today - start).days)
