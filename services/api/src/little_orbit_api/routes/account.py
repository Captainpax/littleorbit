"""Authenticated export and privacy-preserving account deletion lifecycle."""

from base64 import b64encode
from datetime import datetime, timedelta
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..clock import SystemClock
from ..countdown_models import Countdown, CountdownReminder
from ..database import session_scope
from ..dependencies import current_account
from ..interaction_models import Smooch
from ..models import (
    Account,
    Couple,
    CoupleMember,
    DeletionJob,
    LocationSample,
    Note,
    OneUseToken,
    QuizAnswer,
    Session,
    TogetherBucket,
)
from ..profile_models import RelationshipAvatar
from ..schemas import AccountDeletionRequest, AccountDeletionResponse, AccountExportResponse
from ..security import verify_password

router = APIRouter(prefix="/v1/account", tags=["account"])


async def _relationship_export(
    session: AsyncSession, membership: CoupleMember
) -> dict[str, object]:
    notes = list(
        await session.scalars(select(Note).where(Note.couple_id == membership.couple_id))
    )
    countdowns = list(
        await session.scalars(
            select(Countdown).where(Countdown.couple_id == membership.couple_id)
        )
    )
    answers = list(
        await session.scalars(
            select(QuizAnswer).where(QuizAnswer.couple_id == membership.couple_id)
        )
    )
    smooches = list(
        await session.scalars(select(Smooch).where(Smooch.couple_id == membership.couple_id))
    )
    total = await session.scalar(
        select(func.sum(TogetherBucket.duration_seconds)).where(
            TogetherBucket.couple_id == membership.couple_id
        )
    )
    avatars = list(
        await session.scalars(
            select(RelationshipAvatar).where(
                RelationshipAvatar.couple_id == membership.couple_id
            )
        )
    )
    return _relationship_payload(
        membership, notes, countdowns, answers, smooches, avatars, int(total or 0)
    )


def _relationship_payload(
    membership: CoupleMember,
    notes: list[Note],
    countdowns: list[Countdown],
    answers: list[QuizAnswer],
    smooches: list[Smooch],
    avatars: list[RelationshipAvatar],
    together_seconds: int,
) -> dict[str, object]:
    return {
        "couple_id": str(membership.couple_id),
        "joined_at": membership.joined_at,
        "left_at": membership.left_at,
        "notes": [
            {"id": str(item.id), "title": item.title, "body": item.body, "revision": item.revision}
            for item in notes
        ],
        "countdowns": [
            {
                "id": str(item.id),
                "title": item.title,
                "occurs_at": item.occurs_at,
                "timezone": item.timezone,
                "timing_kind": item.timing_kind,
                "occurs_on": item.occurs_on,
                "notes": item.notes,
                "deleted_at": item.deleted_at,
            }
            for item in countdowns
        ],
        "quiz_answers": [
            {
                "question_id": str(item.question_id),
                "account_id": str(item.account_id),
                "answer": item.answer,
                "submitted_at": item.submitted_at,
            }
            for item in answers
        ],
        "estimated_together_seconds": together_seconds,
        "smooches": [_smooch_export(item) for item in smooches],
        "relationship_avatars": [
            {
                "subject_account_id": str(item.subject_account_id),
                "assigned_by_account_id": str(item.assigned_by_account_id),
                "media_type": "image/webp",
                "sha256": item.sha256,
                "revision": item.revision,
                "base64": b64encode(item.image_webp).decode("ascii"),
            }
            for item in avatars
        ],
    }


def _smooch_export(item: Smooch) -> dict[str, UUID | str | datetime | None]:
    """Serialize one relationship signal without adding notification delivery metadata."""

    return {
        "id": str(item.id),
        "sender_id": str(item.sender_id) if item.sender_id else None,
        "recipient_id": str(item.recipient_id) if item.recipient_id else None,
        "emoji": item.emoji,
        "phrase_key": item.phrase_key,
        "sent_at": item.sent_at,
    }


@router.get("/export", response_model=AccountExportResponse)
async def export_account(
    actor: Account = Depends(current_account),
    session: AsyncSession = Depends(session_scope),
) -> AccountExportResponse:
    """Return portable owner-visible data without password, token, or partner coordinates."""

    memberships = list(
        await session.scalars(
            select(CoupleMember)
            .where(CoupleMember.account_id == actor.id)
            .order_by(CoupleMember.joined_at)
        )
    )
    relationships = [
        await _relationship_export(session, membership) for membership in memberships
    ]
    own_samples = list(
        await session.scalars(
            select(LocationSample).where(LocationSample.account_id == actor.id)
        )
    )
    return AccountExportResponse(
        generated_at=SystemClock().now(),
        data={
            "account": {
                "id": str(actor.id),
                "email": actor.email_normalized,
                "display_name": actor.display_name,
                "verified_at": actor.verified_at,
                "created_at": actor.created_at,
                "profile_photo": None,
            },
            "relationships": relationships,
            "unexpired_location_samples": [
                {
                    "sample_id": str(item.sample_id),
                    "recorded_at": item.recorded_at,
                    "latitude": item.latitude,
                    "longitude": item.longitude,
                    "accuracy_m": item.accuracy_m,
                }
                for item in own_samples
            ],
        },
    )


async def _end_active_pairing(session: AsyncSession, actor_id: UUID) -> UUID | None:
    membership = await session.scalar(
        select(CoupleMember)
        .where(CoupleMember.account_id == actor_id, CoupleMember.left_at.is_(None))
        .with_for_update()
    )
    if membership is None:
        return None
    now = SystemClock().now()
    couple = await session.get(Couple, membership.couple_id, with_for_update=True)
    members = list(
        await session.scalars(
            select(CoupleMember)
            .where(
                CoupleMember.couple_id == membership.couple_id,
                CoupleMember.left_at.is_(None),
            )
            .with_for_update()
        )
    )
    if couple:
        couple.ended_at = now
        couple.updated_at = now
    for member in members:
        member.left_at = now
        member.intimacy_enabled = False
        member.location_enabled = False
    await session.execute(
        delete(LocationSample).where(LocationSample.couple_id == membership.couple_id)
    )
    await session.execute(
        delete(RelationshipAvatar).where(
            RelationshipAvatar.couple_id == membership.couple_id
        )
    )
    await session.execute(
        delete(CountdownReminder).where(
            CountdownReminder.countdown_id.in_(
                select(Countdown.id).where(Countdown.couple_id == membership.couple_id)
            )
        )
    )
    return membership.couple_id


@router.post("/deletion", response_model=AccountDeletionResponse)
async def schedule_deletion(
    payload: AccountDeletionRequest,
    request: Request,
    actor: Account = Depends(current_account),
    session: AsyncSession = Depends(session_scope),
) -> AccountDeletionResponse:
    """Reauthenticate, stop access immediately, and schedule full erasure."""

    if not verify_password(actor.password_hash, payload.password):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Password is incorrect")
    now = SystemClock().now()
    execute_after = now + timedelta(days=7)
    couple_id = await _end_active_pairing(session, actor.id)
    actor.deleted_at = now
    actor.updated_at = now
    for active_session in await session.scalars(
        select(Session).where(Session.account_id == actor.id, Session.revoked_at.is_(None))
    ):
        active_session.revoked_at = now
    await session.execute(delete(OneUseToken).where(OneUseToken.account_id == actor.id))
    job = DeletionJob(
        account_id=actor.id,
        execute_after=execute_after,
        status="scheduled",
        requested_at=now,
    )
    session.add(job)
    await session.commit()
    if couple_id:
        from .notes import disconnect_couple_notes

        await disconnect_couple_notes(couple_id, request.app.state.note_connections)
    return AccountDeletionResponse(job_id=job.id, execute_after=execute_after)
