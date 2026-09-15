"""Transactional helpers for RC6 relationship dates and proximity estimates."""

from datetime import UTC, date, datetime, timedelta
from typing import Literal, cast
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import delete, func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from .clock import SystemClock
from .domain.location import Point, TimedPoint, estimate_nearby_minutes
from .models import (
    Couple,
    LocationSample,
    SecurityEvent,
    TogetherBucket,
)
from .schemas import RelationshipStartProposalResponse
from .together_models import RelationshipStartProposal, TogetherDay, TogetherOperation

ALGORITHM_VERSION = 2


def proposal_response(
    proposal: RelationshipStartProposal, actor_id: UUID
) -> RelationshipStartProposalResponse:
    """Map a proposal without exposing any extra account metadata."""

    return RelationshipStartProposalResponse(
        id=proposal.id,
        proposed_date=proposal.proposed_date,
        proposed_by_me=proposal.proposed_by == actor_id,
        status=cast(
            Literal["pending", "accepted", "declined", "cancelled", "expired"],
            proposal.status,
        ),
        expires_at=proposal.expires_at,
    )


async def prior_operation(
    session: AsyncSession, couple_id: UUID, actor_id: UUID, operation_id: UUID
) -> RelationshipStartProposalResponse | None:
    """Return an exact stored retry outcome before reading mutable proposal state."""

    operation = await session.scalar(
        select(TogetherOperation).where(
            TogetherOperation.couple_id == couple_id,
            TogetherOperation.account_id == actor_id,
            TogetherOperation.operation_id == operation_id,
        )
    )
    if operation is None:
        return None
    return RelationshipStartProposalResponse.model_validate(operation.result)


def store_operation(
    session: AsyncSession,
    couple_id: UUID,
    actor_id: UUID,
    operation_id: UUID,
    response: RelationshipStartProposalResponse,
) -> None:
    """Store a content-minimal response for safe mutation retries."""

    session.add(
        TogetherOperation(
            couple_id=couple_id,
            account_id=actor_id,
            operation_id=operation_id,
            result=response.model_dump(mode="json"),
            created_at=SystemClock().now(),
        )
    )


async def pending_proposal(
    session: AsyncSession, couple_id: UUID, lock: bool = False
) -> RelationshipStartProposal | None:
    """Return a live proposal while marking an elapsed proposal expired."""

    query = select(RelationshipStartProposal).where(
        RelationshipStartProposal.couple_id == couple_id,
        RelationshipStartProposal.status == "pending",
    )
    proposal = await session.scalar(query.with_for_update() if lock else query)
    if proposal is None:
        return None
    now = SystemClock().now()
    if proposal.expires_at > now:
        return proposal
    proposal.status = "expired"
    proposal.decided_at = now
    return None


def audit_proposal(
    session: AsyncSession, actor_id: UUID, proposal_id: UUID, outcome: str
) -> None:
    """Record only identifiers and transition outcome in the security audit."""

    session.add(
        SecurityEvent(
            actor_id=actor_id,
            event_type="relationship_start_date",
            outcome=outcome,
            metadata_json={"proposal_id": str(proposal_id)},
            created_at=SystemClock().now(),
        )
    )


async def recompute_recent_proximity(
    session: AsyncSession, couple: Couple, member_ids: list[UUID]
) -> int:
    """Replace recent uncorrected estimates from the current 24-hour raw window."""

    if len(member_ids) != 2:
        raise HTTPException(status.HTTP_409_CONFLICT, "Pairing state changed; retry")
    raw_cutoff = SystemClock().now() - timedelta(hours=24)
    cutoff = raw_cutoff.replace(second=0, microsecond=0)
    samples = list(
        await session.scalars(
            select(LocationSample)
            .where(
                LocationSample.couple_id == couple.id,
                LocationSample.recorded_at >= cutoff,
            )
            .order_by(LocationSample.recorded_at, LocationSample.sample_id)
        )
    )
    streams = [_timed_points(samples, member_id) for member_id in member_ids]
    estimates = estimate_nearby_minutes(
        streams[0], streams[1], couple.proximity_threshold_m
    )
    await session.execute(
        delete(TogetherBucket).where(
            TogetherBucket.couple_id == couple.id,
            TogetherBucket.bucket_start >= cutoff,
            TogetherBucket.corrected_at.is_(None),
        )
    )
    now = SystemClock().now()
    for item in estimates:
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
    couple.proximity_processed_through = _mutual_sample_freshness(streams)
    couple.proximity_algorithm_version = ALGORITHM_VERSION
    couple.updated_at = now
    await _sync_daily_totals(session, couple.id, cutoff, now)
    return sum(item.duration_seconds for item in estimates)


def _mutual_sample_freshness(streams: list[list[TimedPoint]]) -> datetime | None:
    """Return the newest instant supported by a recent sample from both members."""

    if len(streams) != 2 or any(not stream for stream in streams):
        return None
    return min(stream[-1].recorded_at for stream in streams)


async def _sync_daily_totals(
    session: AsyncSession, couple_id: UUID, cutoff: datetime, now: datetime
) -> None:
    """Refresh coordinate-free daily totals while preserving explicit corrections."""

    current_day = cutoff.date()
    final_day = now.astimezone(UTC).date()
    while current_day <= final_day:
        start = datetime.combine(current_day, datetime.min.time(), UTC)
        end = start + timedelta(days=1)
        seconds = int(
            await session.scalar(
                select(func.coalesce(func.sum(TogetherBucket.duration_seconds), 0)).where(
                    TogetherBucket.couple_id == couple_id,
                    TogetherBucket.bucket_start >= start,
                    TogetherBucket.bucket_start < end,
                )
            )
            or 0
        )
        await session.execute(
            insert(TogetherDay)
            .values(
                couple_id=couple_id,
                day=current_day,
                estimated_seconds=min(seconds, 86_400),
                revision=0,
                updated_at=now,
            )
            .on_conflict_do_update(
                index_elements=["couple_id", "day"],
                set_={"estimated_seconds": min(seconds, 86_400), "updated_at": now},
            )
        )
        current_day += timedelta(days=1)


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
