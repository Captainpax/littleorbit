"""Authenticated export and privacy-preserving account deletion lifecycle."""

from base64 import b64encode
from datetime import timedelta
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..clock import SystemClock
from ..database import session_scope
from ..dependencies import current_account
from ..models import (
    Account,
    Countdown,
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
from ..profile_models import AccountProfilePhoto
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
    total = await session.scalar(
        select(func.sum(TogetherBucket.duration_seconds)).where(
            TogetherBucket.couple_id == membership.couple_id
        )
    )
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
        "estimated_together_seconds": int(total or 0),
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
    own_photo = await session.get(AccountProfilePhoto, actor.id)
    return AccountExportResponse(
        generated_at=SystemClock().now(),
        data={
            "account": {
                "id": str(actor.id),
                "email": actor.email_normalized,
                "display_name": actor.display_name,
                "verified_at": actor.verified_at,
                "created_at": actor.created_at,
                "profile_photo": (
                    {
                        "media_type": "image/webp",
                        "sha256": own_photo.sha256,
                        "revision": own_photo.revision,
                        "base64": b64encode(own_photo.image_webp).decode("ascii"),
                    }
                    if own_photo
                    else None
                ),
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
