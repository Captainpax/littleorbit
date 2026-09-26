"""Authenticated export and privacy-preserving account deletion lifecycle."""

from base64 import b64encode
from datetime import datetime, timedelta
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..clock import SystemClock
from ..countdown_models import Countdown
from ..database import session_scope
from ..dependencies import current_account
from ..interaction_models import Smooch
from ..legacy_quiz_privacy import revealed_legacy_answers
from ..models import (
    Account,
    CoupleMember,
    DeletionJob,
    LocationSample,
    Note,
    OneUseToken,
    QuizAnswer,
    Session,
    TogetherBucket,
)
from ..profile_models import RelationshipAvatar, RelationshipName
from ..relationship_service import end_active_relationship, lock_accounts
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
    answers = await revealed_legacy_answers(session, membership.couple_id)
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
    names = list(
        await session.scalars(
            select(RelationshipName).where(
                RelationshipName.couple_id == membership.couple_id
            )
        )
    )
    return _relationship_payload(
        membership, notes, countdowns, answers, smooches, avatars, names, int(total or 0)
    )


def _relationship_payload(
    membership: CoupleMember,
    notes: list[Note],
    countdowns: list[Countdown],
    answers: list[QuizAnswer],
    smooches: list[Smooch],
    avatars: list[RelationshipAvatar],
    names: list[RelationshipName],
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
            _countdown_export(item) for item in countdowns
        ],
        "quiz_answers": [
            _quiz_answer_export(item) for item in answers
        ],
        "estimated_together_seconds": together_seconds,
        "smooches": [_smooch_export(item) for item in smooches],
        "relationship_avatars": [
            _avatar_export(item) for item in avatars
        ],
        "relationship_names": [
            _relationship_name_export(item) for item in names
        ],
    }


def _countdown_export(item: Countdown) -> dict[str, object]:
    return {
        "id": str(item.id),
        "title": item.title,
        "occurs_at": item.occurs_at,
        "timezone": item.timezone,
        "timing_kind": item.timing_kind,
        "occurs_on": item.occurs_on,
        "notes": item.notes,
        "deleted_at": item.deleted_at,
    }


def _quiz_answer_export(item: QuizAnswer) -> dict[str, object]:
    return {
        "question_id": str(item.question_id),
        "account_id": str(item.account_id),
        "answer": item.answer,
        "submitted_at": item.submitted_at,
    }


def _avatar_export(item: RelationshipAvatar) -> dict[str, object]:
    return {
        "subject_account_id": str(item.subject_account_id),
        "assigned_by_account_id": str(item.assigned_by_account_id),
        "media_type": "image/webp",
        "sha256": item.sha256,
        "revision": item.revision,
        "base64": b64encode(item.image_webp).decode("ascii"),
    }


def _relationship_name_export(item: RelationshipName) -> dict[str, object]:
    return {
        "subject_account_id": str(item.subject_account_id),
        "assigned_by_account_id": str(item.assigned_by_account_id),
        "assigned_name": item.assigned_name,
        "revision": item.revision,
        "updated_at": item.updated_at,
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
    couple_id = await end_active_relationship(session, actor.id, now)
    locked_accounts = await lock_accounts(session, (actor.id,))
    locked_actor = locked_accounts[0] if len(locked_accounts) == 1 else None
    if (
        locked_actor is None
        or locked_actor.suspended_at is not None
        or locked_actor.deleted_at is not None
        or not verify_password(locked_actor.password_hash, payload.password)
    ):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Password is incorrect")
    locked_actor.deleted_at = now
    locked_actor.updated_at = now
    for active_session in await session.scalars(
        select(Session).where(
            Session.account_id == locked_actor.id,
            Session.revoked_at.is_(None),
        )
    ):
        active_session.revoked_at = now
    await session.execute(
        delete(OneUseToken).where(OneUseToken.account_id == locked_actor.id)
    )
    job = DeletionJob(
        account_id=locked_actor.id,
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
