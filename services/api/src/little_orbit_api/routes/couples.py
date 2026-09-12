"""Couple consent, unpairing, and private read-only archive routes."""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..clock import SystemClock
from ..couple_access import active_member, both_members_consent
from ..database import session_scope
from ..dependencies import current_account
from ..models import (
    Account,
    Countdown,
    Couple,
    CoupleMember,
    LocationSample,
    Note,
    QuizAnswer,
)
from ..quiz_v2_service import revoke_unrevealed_intimacy
from ..schemas import (
    ArchiveDetail,
    ArchiveSummary,
    CouplePreferencesRequest,
    CouplePreferencesResponse,
    UnpairResponse,
)

router = APIRouter(prefix="/v1/couple", tags=["couple"])


async def _preferences(
    session: AsyncSession, member: CoupleMember
) -> CouplePreferencesResponse:
    couple = await session.get(Couple, member.couple_id)
    if couple is None:
        raise HTTPException(status.HTTP_409_CONFLICT, "Pairing state is unavailable")
    return CouplePreferencesResponse(
        couple_id=couple.id,
        anniversary_date=couple.anniversary_date,
        proximity_threshold_m=couple.proximity_threshold_m,
        intimacy_enabled_by_me=member.intimacy_enabled,
        intimacy_enabled_by_both=await both_members_consent(
            session, couple.id, "intimacy_enabled"
        ),
        location_enabled_by_me=member.location_enabled,
        location_enabled_by_both=await both_members_consent(
            session, couple.id, "location_enabled"
        ),
    )


@router.get("/preferences", response_model=CouplePreferencesResponse)
async def get_preferences(
    actor: Account = Depends(current_account),
    session: AsyncSession = Depends(session_scope),
) -> CouplePreferencesResponse:
    """Read consent without inferring one partner's private reason for declining."""

    return await _preferences(session, await active_member(session, actor.id))


@router.patch("/preferences", response_model=CouplePreferencesResponse)
async def update_preferences(
    payload: CouplePreferencesRequest,
    actor: Account = Depends(current_account),
    session: AsyncSession = Depends(session_scope),
) -> CouplePreferencesResponse:
    """Apply revocable member consent and shared estimate settings transactionally."""

    member = await active_member(session, actor.id, lock=True)
    couple = await session.get(Couple, member.couple_id, with_for_update=True)
    if couple is None:
        raise HTTPException(status.HTTP_409_CONFLICT, "Pairing state is unavailable")
    if payload.intimacy_enabled is not None:
        member.intimacy_enabled = payload.intimacy_enabled
        if not payload.intimacy_enabled:
            await revoke_unrevealed_intimacy(session, member.couple_id)
    if payload.location_enabled is not None:
        member.location_enabled = payload.location_enabled
        if not payload.location_enabled:
            await session.execute(
                delete(LocationSample).where(LocationSample.account_id == actor.id)
            )
    if payload.proximity_threshold_m is not None:
        couple.proximity_threshold_m = payload.proximity_threshold_m
    if "anniversary_date" in payload.model_fields_set:
        couple.anniversary_date = payload.anniversary_date
    couple.updated_at = SystemClock().now()
    await session.commit()
    return await _preferences(session, member)


@router.post("/unpair", response_model=UnpairResponse)
async def unpair(
    request: Request,
    actor: Account = Depends(current_account),
    session: AsyncSession = Depends(session_scope),
) -> UnpairResponse:
    """End all sharing immediately while retaining each member's private archive."""

    member = await active_member(session, actor.id, lock=True)
    couple = await session.get(Couple, member.couple_id, with_for_update=True)
    members = list(
        await session.scalars(
            select(CoupleMember)
            .where(
                CoupleMember.couple_id == member.couple_id,
                CoupleMember.left_at.is_(None),
            )
            .with_for_update()
        )
    )
    if couple is None or len(members) != 2:
        raise HTTPException(status.HTTP_409_CONFLICT, "Pairing state changed; retry")
    ended_at = SystemClock().now()
    couple.ended_at = ended_at
    couple.updated_at = ended_at
    for current in members:
        current.left_at = ended_at
        current.intimacy_enabled = False
        current.location_enabled = False
    await session.execute(
        delete(LocationSample).where(LocationSample.couple_id == couple.id)
    )
    await session.commit()
    from .notes import disconnect_couple_notes

    await disconnect_couple_notes(couple.id, request.app.state.note_connections)
    return UnpairResponse(archive_id=couple.id, ended_at=ended_at)


async def _archive_membership(
    session: AsyncSession, account_id: UUID, couple_id: UUID
) -> CoupleMember:
    membership = await session.scalar(
        select(CoupleMember).where(
            CoupleMember.account_id == account_id,
            CoupleMember.couple_id == couple_id,
            CoupleMember.left_at.is_not(None),
        )
    )
    if membership is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Archive is unavailable")
    return membership


async def _archive_summary(
    session: AsyncSession, membership: CoupleMember
) -> ArchiveSummary:
    partner_name = await session.scalar(
        select(Account.display_name)
        .join(CoupleMember, CoupleMember.account_id == Account.id)
        .where(
            CoupleMember.couple_id == membership.couple_id,
            CoupleMember.account_id != membership.account_id,
        )
    )
    return ArchiveSummary(
        archive_id=membership.couple_id,
        partner_display_name=partner_name or "Former partner",
        joined_at=membership.joined_at,
        ended_at=membership.left_at or membership.joined_at,
    )


@router.get("/archives", response_model=list[ArchiveSummary])
async def list_archives(
    actor: Account = Depends(current_account),
    session: AsyncSession = Depends(session_scope),
) -> list[ArchiveSummary]:
    """List only former pairings that belonged to the authenticated account."""

    memberships = list(
        await session.scalars(
            select(CoupleMember)
            .where(
                CoupleMember.account_id == actor.id,
                CoupleMember.left_at.is_not(None),
            )
            .order_by(CoupleMember.left_at.desc())
        )
    )
    return [await _archive_summary(session, item) for item in memberships]


@router.get("/archives/{archive_id}", response_model=ArchiveDetail)
async def archive_detail(
    archive_id: UUID,
    actor: Account = Depends(current_account),
    session: AsyncSession = Depends(session_scope),
) -> ArchiveDetail:
    """Read immutable content from one former couple without restoring sharing."""

    membership = await _archive_membership(session, actor.id, archive_id)
    summary = await _archive_summary(session, membership)
    notes = list(await session.scalars(select(Note).where(Note.couple_id == archive_id)))
    countdowns = list(
        await session.scalars(select(Countdown).where(Countdown.couple_id == archive_id))
    )
    answers = list(
        await session.scalars(select(QuizAnswer).where(QuizAnswer.couple_id == archive_id))
    )
    return ArchiveDetail(
        **summary.model_dump(),
        notes=[
            {"id": str(item.id), "title": item.title, "body": item.body, "revision": item.revision}
            for item in notes
        ],
        countdowns=[
            {
                "id": str(item.id),
                "title": item.title,
                "occurs_at": item.occurs_at,
                "timezone": item.timezone,
                "notes": item.notes,
            }
            for item in countdowns
        ],
        quiz_answers=[
            {
                "question_id": str(item.question_id),
                "account_id": str(item.account_id),
                "answer": item.answer,
                "submitted_at": item.submitted_at,
            }
            for item in answers
        ],
    )
