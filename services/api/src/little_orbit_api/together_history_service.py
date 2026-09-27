"""Coordinate-free shared-home day boundaries and evidence summaries."""

from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta
from uuid import UUID
from zoneinfo import ZoneInfo

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from .models import TogetherBucket


@dataclass(frozen=True)
class DayBreakdown:
    """Coordinate-free component totals for one local calendar day."""

    observed: int
    bridged: int
    unverified: int
    apart: int
    poor_accuracy: int


def timezone_or_utc(name: str) -> ZoneInfo:
    """Resolve an IANA timezone with a legacy-data fallback."""

    try:
        return ZoneInfo(name)
    except (KeyError, ValueError):
        return ZoneInfo("UTC")


def day_bounds(target: date, timezone_name: str) -> tuple[datetime, datetime]:
    """Return UTC boundaries for a shared-home day, including DST changes."""

    timezone = timezone_or_utc(timezone_name)
    start = datetime.combine(target, time.min, timezone).astimezone(UTC)
    end = datetime.combine(target + timedelta(days=1), time.min, timezone).astimezone(UTC)
    return start, end


async def day_breakdown(
    session: AsyncSession,
    couple_id: UUID,
    target: date,
    timezone_name: str,
) -> DayBreakdown:
    """Sum only coordinate-free evidence components for a local day."""

    start, end = day_bounds(target, timezone_name)
    row = (
        await session.execute(
            select(
                func.coalesce(func.sum(TogetherBucket.observed_seconds), 0),
                func.coalesce(func.sum(TogetherBucket.bridged_seconds), 0),
                func.coalesce(func.sum(TogetherBucket.unverified_seconds), 0),
                func.coalesce(func.sum(TogetherBucket.apart_seconds), 0),
                func.coalesce(func.sum(TogetherBucket.poor_accuracy_seconds), 0),
            ).where(
                TogetherBucket.couple_id == couple_id,
                TogetherBucket.bucket_start >= start,
                TogetherBucket.bucket_start < end,
            )
        )
    ).one()
    return DayBreakdown(*(int(value or 0) for value in row))
