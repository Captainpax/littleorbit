"""RC6 relationship age, mutual start date, and deterministic proximity routes."""

from datetime import UTC, datetime, timedelta
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from ..clock import SystemClock
from ..couple_access import active_member, both_members_consent
from ..database import session_scope
from ..dependencies import current_account
from ..models import (
    Account,
    Couple,
    CoupleMember,
    LocationSample,
    TogetherBucket,
)
from ..schemas import (
    LocationBatchRequest,
    LocationBatchV2Response,
    RelationshipStartDecisionRequest,
    RelationshipStartProposalRequest,
    RelationshipStartProposalResponse,
    TogetherHistoryDay,
    TogetherSummaryV2,
)
from ..together_models import RelationshipStartProposal
from ..together_time_service import (
    audit_proposal,
    pending_proposal,
    prior_operation,
    proposal_response,
    recompute_recent_proximity,
    relationship_days,
    store_operation,
)

router = APIRouter(prefix="/v2/together-time", tags=["together-time-v2"])


async def _locked_couple(session: AsyncSession, couple_id: UUID) -> Couple:
    couple = await session.get(Couple, couple_id, with_for_update=True)
    if couple is None:
        raise HTTPException(status.HTTP_409_CONFLICT, "Pairing state is unavailable")
    return couple


@router.get("", response_model=TogetherSummaryV2)
async def together_summary_v2(
    actor: Account = Depends(current_account),
    session: AsyncSession = Depends(session_scope),
) -> TogetherSummaryV2:
    """Return relationship age and location-derived nearby time as separate values."""

    member = await active_member(session, actor.id)
    couple = await session.get(Couple, member.couple_id)
    if couple is None:
        raise HTTPException(status.HTTP_409_CONFLICT, "Pairing state is unavailable")
    total = await session.scalar(
        select(func.coalesce(func.sum(TogetherBucket.duration_seconds), 0)).where(
            TogetherBucket.couple_id == couple.id
        )
    )
    proposal = await pending_proposal(session, couple.id)
    return TogetherSummaryV2(
        relationship_start_date=couple.anniversary_date,
        relationship_days=relationship_days(couple.anniversary_date),
        nearby_estimated_seconds=int(total or 0),
        nearby_last_processed_at=couple.proximity_processed_through,
        proximity_threshold_m=couple.proximity_threshold_m,
        location_enabled_by_me=member.location_enabled,
        location_enabled_by_both=await both_members_consent(
            session, couple.id, "location_enabled"
        ),
        label="estimate",
        pending_start_date=proposal_response(proposal, actor.id) if proposal else None,
    )


@router.get("/history", response_model=list[TogetherHistoryDay])
async def together_history(
    days: Annotated[int, Query(ge=1, le=30)] = 30,
    actor: Account = Depends(current_account),
    session: AsyncSession = Depends(session_scope),
) -> list[TogetherHistoryDay]:
    """Return up to thirty complete UTC calendar days without coordinates."""

    member = await active_member(session, actor.id)
    today = SystemClock().now().astimezone(UTC).date()
    cutoff = datetime.combine(today - timedelta(days=days - 1), datetime.min.time(), UTC)
    buckets = list(
        await session.scalars(
            select(TogetherBucket).where(
                TogetherBucket.couple_id == member.couple_id,
                TogetherBucket.bucket_start >= cutoff,
            )
        )
    )
    totals: dict[object, int] = {}
    corrected: set[object] = set()
    for bucket in buckets:
        day = bucket.bucket_start.astimezone(UTC).date()
        totals[day] = totals.get(day, 0) + bucket.duration_seconds
        if bucket.corrected_at is not None:
            corrected.add(day)
    return [
        TogetherHistoryDay(
            day=today - timedelta(days=offset),
            estimated_seconds=totals.get(today - timedelta(days=offset), 0),
            corrected=today - timedelta(days=offset) in corrected,
        )
        for offset in range(days - 1, -1, -1)
    ]


@router.post(
    "/start-date-proposals", response_model=RelationshipStartProposalResponse
)
async def propose_start_date(
    payload: RelationshipStartProposalRequest,
    actor: Account = Depends(current_account),
    session: AsyncSession = Depends(session_scope),
) -> RelationshipStartProposalResponse:
    """Create or replace the caller's pending proposal for partner review."""

    member = await active_member(session, actor.id, lock=True)
    couple = await _locked_couple(session, member.couple_id)
    prior = await prior_operation(session, couple.id, actor.id, payload.operation_id)
    if prior is not None:
        return prior
    if payload.proposed_date > SystemClock().now().astimezone(UTC).date():
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Start date cannot be future")
    current = await pending_proposal(session, couple.id, lock=True)
    now = SystemClock().now()
    if current is not None and current.proposed_by != actor.id:
        raise HTTPException(status.HTTP_409_CONFLICT, "Partner proposal awaits your decision")
    if current is not None:
        current.status = "cancelled"
        current.decided_by = actor.id
        current.decided_at = now
    proposal = RelationshipStartProposal(
        couple_id=couple.id,
        proposed_by=actor.id,
        proposed_date=payload.proposed_date,
        status="pending",
        expires_at=now + timedelta(days=7),
        created_at=now,
    )
    session.add(proposal)
    await session.flush()
    response = proposal_response(proposal, actor.id)
    store_operation(session, couple.id, actor.id, payload.operation_id, response)
    audit_proposal(session, actor.id, proposal.id, "proposed")
    await session.commit()
    return response


@router.post(
    "/start-date-proposals/{proposal_id}/decision",
    response_model=RelationshipStartProposalResponse,
)
async def decide_start_date(
    proposal_id: UUID,
    payload: RelationshipStartDecisionRequest,
    actor: Account = Depends(current_account),
    session: AsyncSession = Depends(session_scope),
) -> RelationshipStartProposalResponse:
    """Accept, decline, or cancel one current proposal with role checks."""

    member = await active_member(session, actor.id, lock=True)
    couple = await _locked_couple(session, member.couple_id)
    prior = await prior_operation(session, couple.id, actor.id, payload.operation_id)
    if prior is not None:
        return prior
    proposal = await session.scalar(
        select(RelationshipStartProposal)
        .where(
            RelationshipStartProposal.id == proposal_id,
            RelationshipStartProposal.couple_id == couple.id,
        )
        .with_for_update()
    )
    _require_current_decision(proposal, actor.id, payload.decision)
    assert proposal is not None
    now = SystemClock().now()
    proposal.status = {"accept": "accepted", "decline": "declined", "cancel": "cancelled"}[
        payload.decision
    ]
    proposal.decided_by = actor.id
    proposal.decided_at = now
    if payload.decision == "accept":
        couple.anniversary_date = proposal.proposed_date
        couple.updated_at = now
    response = proposal_response(proposal, actor.id)
    store_operation(session, couple.id, actor.id, payload.operation_id, response)
    audit_proposal(session, actor.id, proposal.id, proposal.status)
    await session.commit()
    return response


def _require_current_decision(
    proposal: RelationshipStartProposal | None, actor_id: UUID, decision: str
) -> None:
    if proposal is None or proposal.status != "pending":
        raise HTTPException(status.HTTP_409_CONFLICT, "Proposal state changed; refresh")
    if proposal.expires_at <= SystemClock().now():
        proposal.status = "expired"
        proposal.decided_at = SystemClock().now()
        raise HTTPException(status.HTTP_409_CONFLICT, "Proposal expired; refresh")
    proposer = proposal.proposed_by == actor_id
    if (decision == "cancel") != proposer:
        raise HTTPException(status.HTTP_409_CONFLICT, "Decision is not available to this member")


@router.post("/locations", response_model=LocationBatchV2Response)
async def upload_locations_v2(
    payload: LocationBatchRequest,
    actor: Account = Depends(current_account),
    session: AsyncSession = Depends(session_scope),
) -> LocationBatchV2Response:
    """Store a bounded retry-safe batch only while both partners consent."""

    member = await active_member(session, actor.id, lock=True)
    couple = await _locked_couple(session, member.couple_id)
    if not await both_members_consent(session, couple.id, "location_enabled"):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Mutual location sharing is disabled")
    accepted = 0
    for sample in payload.samples:
        _validate_sample_time(sample.recorded_at)
        stored = await session.scalar(
            insert(LocationSample)
            .values(
                sample_id=sample.sample_id,
                account_id=actor.id,
                couple_id=couple.id,
                recorded_at=sample.recorded_at.astimezone(UTC),
                latitude=sample.latitude,
                longitude=sample.longitude,
                accuracy_m=sample.accuracy_m,
                expires_at=min(
                    SystemClock().now() + timedelta(hours=24),
                    sample.recorded_at.astimezone(UTC) + timedelta(hours=24),
                ),
            )
            .on_conflict_do_nothing(index_elements=["account_id", "sample_id"])
            .returning(LocationSample.id)
        )
        accepted += stored is not None
    member_ids = list(
        await session.scalars(
            select(CoupleMember.account_id)
            .where(CoupleMember.couple_id == couple.id, CoupleMember.left_at.is_(None))
            .order_by(CoupleMember.account_id)
        )
    )
    seconds = await recompute_recent_proximity(session, couple, member_ids)
    await session.commit()
    return LocationBatchV2Response(
        accepted=accepted,
        duplicates=len(payload.samples) - accepted,
        nearby_seconds_recomputed=seconds,
    )


def _validate_sample_time(recorded_at: datetime) -> None:
    if recorded_at.tzinfo is None:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "recorded_at needs an offset")
    instant = recorded_at.astimezone(UTC)
    now = SystemClock().now()
    if instant < now - timedelta(hours=24) or instant > now + timedelta(minutes=5):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "sample time is outside policy")
