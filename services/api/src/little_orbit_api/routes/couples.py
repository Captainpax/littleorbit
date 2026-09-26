"""Couple consent, unpairing, and private read-only archive routes."""

from uuid import UUID
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..attachment_models import NoteAttachment
from ..attachment_responses import attachment_response
from ..clock import SystemClock
from ..countdown_models import Countdown
from ..couple_access import (
    active_member,
    archived_member,
    both_members_consent,
    lock_couple,
    relationship_inactive_error,
)
from ..database import session_scope
from ..dependencies import current_account
from ..interaction_models import Smooch
from ..legacy_quiz_privacy import revealed_legacy_answers
from ..models import (
    Account,
    Couple,
    CoupleMember,
    LocationSample,
    Note,
    QuizAnswer,
)
from ..quiz_v2_service import revoke_unrevealed_intimacy
from ..relationship_service import end_active_relationship
from ..schemas import (
    ArchiveDetail,
    ArchiveNote,
    ArchiveSummary,
    CouplePreferencesRequest,
    CouplePreferencesResponse,
    UnpairResponse,
)

router = APIRouter(prefix="/v1/couple", tags=["couple"])


async def _preferences(session: AsyncSession, member: CoupleMember) -> CouplePreferencesResponse:
    couple = await session.get(Couple, member.couple_id)
    if couple is None or couple.ended_at is not None:
        raise relationship_inactive_error()
    return CouplePreferencesResponse(
        couple_id=couple.id,
        anniversary_date=couple.anniversary_date,
        proximity_threshold_m=couple.proximity_threshold_m,
        intimacy_enabled_by_me=member.intimacy_enabled,
        intimacy_enabled_by_both=await both_members_consent(session, couple.id, "intimacy_enabled"),
        location_enabled_by_me=member.location_enabled,
        location_enabled_by_both=await both_members_consent(session, couple.id, "location_enabled"),
        home_timezone=couple.home_timezone,
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

    member = await active_member(session, actor.id)
    couple = await lock_couple(session, member.couple_id)
    if payload.intimacy_enabled is not None:
        member.intimacy_enabled = payload.intimacy_enabled
        if not payload.intimacy_enabled:
            await revoke_unrevealed_intimacy(session, member.couple_id)
    if payload.location_enabled is not None:
        member.location_enabled = payload.location_enabled
        if not payload.location_enabled:
            await session.execute(
                delete(LocationSample).where(LocationSample.couple_id == couple.id)
            )
    if payload.proximity_threshold_m is not None:
        couple.proximity_threshold_m = payload.proximity_threshold_m
    if payload.home_timezone is not None:
        try:
            ZoneInfo(payload.home_timezone)
        except ZoneInfoNotFoundError as exc:
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_ENTITY, "Timezone is invalid"
            ) from exc
        couple.home_timezone = payload.home_timezone
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

    ended_at = SystemClock().now()
    couple_id = await end_active_relationship(session, actor.id, ended_at)
    if couple_id is None:
        raise relationship_inactive_error()
    await session.commit()
    from .notes import disconnect_couple_notes

    await disconnect_couple_notes(couple_id, request.app.state.note_connections)
    return UnpairResponse(archive_id=couple_id, ended_at=ended_at)


async def _archive_summary(session: AsyncSession, membership: CoupleMember) -> ArchiveSummary:
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

    membership = await archived_member(session, actor.id, archive_id)
    summary = await _archive_summary(session, membership)
    notes = list(await session.scalars(select(Note).where(Note.couple_id == archive_id)))
    attachments = list(
        await session.scalars(
            select(NoteAttachment).where(
                NoteAttachment.couple_id == archive_id,
                NoteAttachment.status == "available",
                NoteAttachment.deleted_at.is_(None),
            )
        )
    )
    attachments_by_note: dict[UUID, list[NoteAttachment]] = {}
    for item in attachments:
        attachments_by_note.setdefault(item.note_id, []).append(item)
    countdowns = list(
        await session.scalars(select(Countdown).where(Countdown.couple_id == archive_id))
    )
    answers = await revealed_legacy_answers(session, archive_id)
    smooches = list(await session.scalars(select(Smooch).where(Smooch.couple_id == archive_id)))
    return ArchiveDetail(
        **summary.model_dump(),
        notes=[
            _archive_note(item, archive_id, attachments_by_note.get(item.id, [])) for item in notes
        ],
        countdowns=[_archive_countdown(item) for item in countdowns],
        quiz_answers=[_archive_answer(item) for item in answers],
        smooches=[_archive_smooch(item) for item in smooches],
    )


def _archive_countdown(item: Countdown) -> dict[str, object]:
    return {
        "id": str(item.id),
        "title": item.title,
        "occurs_at": item.occurs_at,
        "timezone": item.timezone,
        "timing_kind": item.timing_kind,
        "occurs_on": item.occurs_on,
        "notes": item.notes,
    }


def _archive_answer(item: QuizAnswer) -> dict[str, object]:
    return {
        "question_id": str(item.question_id),
        "account_id": str(item.account_id),
        "answer": item.answer,
        "submitted_at": item.submitted_at,
    }


def _archive_smooch(item: Smooch) -> dict[str, object]:
    return {
        "id": str(item.id),
        "sender_id": str(item.sender_id) if item.sender_id else None,
        "recipient_id": str(item.recipient_id) if item.recipient_id else None,
        "emoji": item.emoji,
        "phrase_key": item.phrase_key,
        "sent_at": item.sent_at,
    }


def _archive_note(note: Note, archive_id: UUID, attachments: list[NoteAttachment]) -> ArchiveNote:
    """Build one typed archive note after the route authorized former membership."""

    return ArchiveNote(
        id=note.id,
        title=note.title,
        body=note.body,
        revision=note.revision,
        attachments=[
            attachment_response(
                item,
                download_url=(
                    f"/api/v1/couple/archives/{archive_id}/notes/{note.id}"
                    f"/attachments/{item.id}/content"
                ),
            )
            for item in sorted(attachments, key=lambda value: value.created_at)
        ],
    )
