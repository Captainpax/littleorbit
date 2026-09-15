"""RC6 relationship age, mutual start date, and deterministic proximity routes."""

from datetime import UTC, date, datetime, timedelta
from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from ..clock import SystemClock
from ..couple_access import active_member, both_members_consent, relationship_inactive_error
from ..database import session_scope
from ..dependencies import current_account
from ..domain.location import raw_location_expires_at
from ..models import (
    Account,
    Couple,
    CoupleMember,
    LocationSample,
    TogetherBucket,
)
from ..notification_service import enqueue_together_correction_event
from ..schemas import (
    LocationBatchRequest,
    LocationBatchV2Response,
    RelationshipStartDecisionRequest,
    RelationshipStartProposalRequest,
    RelationshipStartProposalResponse,
    TogetherDayCorrectionRequest,
    TogetherHistoryDay,
    TogetherSummaryV2,
    TogetherSummaryV3,
)
from ..together_models import RelationshipStartProposal, TogetherDay
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


@router.get("", response_model=TogetherSummaryV2)
async def together_summary_v2(
    actor: Account = Depends(current_account),
    session: AsyncSession = Depends(session_scope),
) -> TogetherSummaryV2:
    """Return relationship age and location-derived nearby time as separate values."""

    member = await active_member(session, actor.id)
    couple = await session.get(Couple, member.couple_id)
    if couple is None or couple.ended_at is not None:
        raise relationship_inactive_error()
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
    total = await session.scalar(
        select(
            func.coalesce(
                func.sum(func.coalesce(TogetherDay.corrected_seconds, TogetherDay.estimated_seconds)),
                0,
            )
        ).where(TogetherDay.couple_id == couple.id)
    )
    paired_days = max(0, (SystemClock().now() - couple.created_at).days)
    return TogetherSummaryV3(
        paired_at=couple.created_at,
        paired_days=paired_days,
        nearby_estimated_seconds=int(total or 0),
        nearby_last_processed_at=couple.proximity_processed_through,
        nearby_confidence=_confidence(couple.proximity_processed_through),
        proximity_threshold_m=couple.proximity_threshold_m,
        location_enabled_by_me=member.location_enabled,
        location_enabled_by_both=await both_members_consent(
            session, couple.id, "location_enabled"
        ),
        label="estimate",
    )


@v3_router.get("/history", response_model=list[TogetherHistoryDay])
@router.get("/history", response_model=list[TogetherHistoryDay])
async def together_history(
    days: Annotated[int, Query(ge=1, le=30)] = 30,
    actor: Account = Depends(current_account),
    session: AsyncSession = Depends(session_scope),
) -> list[TogetherHistoryDay]:
    """Return up to thirty complete UTC calendar days without coordinates."""

    member = await active_member(session, actor.id)
    today = SystemClock().now().astimezone(UTC).date()
    cutoff = today - timedelta(days=days - 1)
    records = list(
        await session.scalars(
            select(TogetherDay).where(
                TogetherDay.couple_id == member.couple_id,
                TogetherDay.day >= cutoff,
            )
        )
    )
    names = {
        account_id: await session.scalar(
            select(Account.display_name).where(Account.id == account_id)
        )
        for account_id in {item.corrected_by for item in records if item.corrected_by}
    }
    by_day = {item.day: item for item in records}
    return [
        _history_response(today - timedelta(days=offset), by_day, names)
        for offset in range(days - 1, -1, -1)
    ]


def _history_response(
    day: date, records: dict[date, TogetherDay], names: dict[UUID, str | None]
) -> TogetherHistoryDay:
    item = records.get(day)
    if item is None:
        return TogetherHistoryDay(day=day, estimated_seconds=0, corrected=False)
    return TogetherHistoryDay(
        day=day,
        estimated_seconds=item.effective_seconds,
        corrected=item.corrected_seconds is not None,
        revision=item.revision,
        corrected_by_display_name=names.get(item.corrected_by) if item.corrected_by else None,
        correction_reason=item.correction_reason,
    )


def _confidence(
    processed_at: datetime | None,
) -> Literal["unavailable", "low", "medium", "high"]:
    if processed_at is None:
        return "unavailable"
    age = SystemClock().now() - processed_at
    if age <= timedelta(minutes=30):
        return "high"
    if age <= timedelta(hours=2):
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
    """Apply an optimistic correction to one completed UTC day and notify the partner."""

    member = await active_member(session, actor.id)
    couple = await _locked_couple(session, member.couple_id)
    today = SystemClock().now().astimezone(UTC).date()
    if target_day >= today or target_day < couple.created_at.astimezone(UTC).date():
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Choose a completed paired day")
    item = await session.scalar(
        select(TogetherDay)
        .where(TogetherDay.couple_id == couple.id, TogetherDay.day == target_day)
        .with_for_update()
    )
    if item is None:
        item = TogetherDay(
            couple_id=couple.id,
            day=target_day,
            estimated_seconds=await _bucket_total(session, couple.id, target_day),
            revision=0,
            updated_at=SystemClock().now(),
        )
        session.add(item)
        await session.flush()
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
    return TogetherHistoryDay(
        day=target_day,
        estimated_seconds=item.effective_seconds,
        corrected=True,
        revision=item.revision,
        corrected_by_display_name=actor.display_name,
        correction_reason=item.correction_reason,
    )


async def _bucket_total(session: AsyncSession, couple_id: UUID, target_day: date) -> int:
    start = datetime.combine(target_day, datetime.min.time(), UTC)
    value = await session.scalar(
        select(func.coalesce(func.sum(TogetherBucket.duration_seconds), 0)).where(
            TogetherBucket.couple_id == couple_id,
            TogetherBucket.bucket_start >= start,
            TogetherBucket.bucket_start < start + timedelta(days=1),
        )
    )
    return min(int(value or 0), 86_400)


@router.post(
    "/start-date-proposals", response_model=RelationshipStartProposalResponse
)
async def propose_start_date(
    payload: RelationshipStartProposalRequest,
    actor: Account = Depends(current_account),
    session: AsyncSession = Depends(session_scope),
) -> RelationshipStartProposalResponse:
    """Create or replace the caller's pending proposal for partner review."""

    member = await active_member(session, actor.id)
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

    member = await active_member(session, actor.id)
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


@v3_router.post("/location-batches", response_model=LocationBatchV2Response)
@router.post("/locations", response_model=LocationBatchV2Response)
async def upload_locations_v2(
    payload: LocationBatchRequest,
    actor: Account = Depends(current_account),
    session: AsyncSession = Depends(session_scope),
) -> LocationBatchV2Response:
    """Store a bounded retry-safe batch only while both partners consent."""

    member = await active_member(session, actor.id)
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
                expires_at=raw_location_expires_at(sample.recorded_at),
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
    if raw_location_expires_at(instant) <= now or instant > now + timedelta(minutes=5):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "sample time is outside policy")
