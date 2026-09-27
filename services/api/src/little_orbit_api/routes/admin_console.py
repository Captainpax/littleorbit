"""Privacy-limited owner console operations beyond MFA and configuration."""

from datetime import date
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from little_orbit_ai.pipeline import load_curated_bank
from little_orbit_ai.schemas import CandidateQuestion, Category, IconKey, QuestionKind
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql.elements import ColumnElement

from ..attachment_models import NoteAttachment
from ..big_orbit_dependencies import current_big_orbit_account as current_admin
from ..clock import SystemClock
from ..database import session_scope
from ..models import (
    Account,
    ApkRelease,
    Couple,
    CoupleMember,
    CuratedBankQuestion,
    DeletionJob,
    GenerationBatch,
    MailOutbox,
    Question,
    QuestionReport,
    QuizAnswer,
    QuizDayQuestion,
    RuntimeSetting,
    SecurityEvent,
    Session,
)
from ..notification_models import NotificationDevice
from ..release_service import PublishedReleaseImmutable, upsert_apk_release
from ..schemas import (
    AdminAccountAction,
    AdminCollectionResponse,
    AdminOverviewResponse,
    AdminQuestionAction,
    AdminRegistrationControl,
    ApkReleaseInput,
    CuratedImportRequest,
    CuratedQuestionInput,
    PublicMessage,
)

router = APIRouter(prefix="/v2/admin", tags=["administration"])


async def _row_count(
    session: AsyncSession, model: type[Any], *filters: ColumnElement[bool]
) -> int:
    value = await session.scalar(select(func.count()).select_from(model).where(*filters))
    return int(value or 0)


@router.get("/overview", response_model=AdminOverviewResponse)
async def overview(
    _admin: Account = Depends(current_admin),
    session: AsyncSession = Depends(session_scope),
) -> AdminOverviewResponse:
    """Return service and metadata counters without relationship content."""

    today = date.today()
    covered = await _row_count(
        session,
        GenerationBatch,
        GenerationBatch.publish_date >= today,
    )
    values: dict[str, object] = {
        "services": {
            "api": "operational",
            "database": "operational",
            "email_pending": await _row_count(
                session, MailOutbox, MailOutbox.delivered_at.is_(None)
            ),
            "ollama": "validated" if covered else "awaiting_first_batch",
            "scheduler": "covered" if covered >= 7 else "building_coverage",
            "scheduler_days_covered": covered,
            "storage": "operational",
            "attachment_scan_pending": await _row_count(
                session, NoteAttachment, NoteAttachment.status.in_(("pending_scan", "scanning"))
            ),
            "attachment_rejected": await _row_count(
                session, NoteAttachment, NoteAttachment.status == "rejected"
            ),
            "release": "published"
            if await _row_count(session, ApkRelease, ApkRelease.published_at.is_not(None))
            else "not_published",
        },
        "accounts": await _row_count(session, Account, Account.deleted_at.is_(None)),
        "active_couples": await _row_count(session, Couple, Couple.ended_at.is_(None)),
        "question_reports": await _row_count(
            session, QuestionReport, QuestionReport.resolved_at.is_(None)
        ),
        "deletion_jobs": await _row_count(
            session, DeletionJob, DeletionJob.status == "scheduled"
        ),
    }
    return AdminOverviewResponse(values=values)


@router.get("/accounts", response_model=AdminCollectionResponse)
async def accounts(
    limit: int = Query(default=50, ge=1, le=100),
    _admin: Account = Depends(current_admin),
    session: AsyncSession = Depends(session_scope),
) -> AdminCollectionResponse:
    """List bounded account metadata without answers, notes, exports, or locations."""

    records = list(
        await session.scalars(select(Account).order_by(Account.created_at.desc()).limit(limit))
    )
    return AdminCollectionResponse(
        items=[
            {
                "id": str(item.id),
                "email": item.email_normalized,
                "display_name": item.display_name,
                "verified_at": item.verified_at,
                "suspended_at": item.suspended_at,
                "deleted_at": item.deleted_at,
                "is_admin": item.is_admin,
                "created_at": item.created_at,
            }
            for item in records
        ]
    )


@router.patch("/accounts/{account_id}", response_model=PublicMessage)
async def update_account(
    account_id: UUID,
    payload: AdminAccountAction,
    admin: Account = Depends(current_admin),
    session: AsyncSession = Depends(session_scope),
) -> PublicMessage:
    """Suspend or restore an account and revoke sessions when suspending."""

    account = await session.get(Account, account_id, with_for_update=True)
    if account is None or account.deleted_at is not None or account.id == admin.id:
        raise HTTPException(status.HTTP_409_CONFLICT, "Account cannot be changed")
    now = SystemClock().now()
    account.suspended_at = now if payload.suspended else None
    if payload.suspended:
        sessions = await session.scalars(
            select(Session).where(Session.account_id == account.id, Session.revoked_at.is_(None))
        )
        for active_session in sessions:
            active_session.revoked_at = now
        devices = await session.scalars(
            select(NotificationDevice).where(NotificationDevice.account_id == account.id)
        )
        for device in devices:
            device.notifications_enabled = False
            device.disabled_at = now
    session.add(
        SecurityEvent(
            actor_id=admin.id,
            event_type="admin_account_status",
            outcome="suspended" if payload.suspended else "restored",
            metadata_json={"account_id": str(account.id)},
            created_at=now,
        )
    )
    await session.commit()
    return PublicMessage(message="Account status updated.")


@router.post("/accounts/{account_id}/revoke-sessions", response_model=PublicMessage)
async def revoke_account_sessions(
    account_id: UUID,
    admin: Account = Depends(current_admin),
    session: AsyncSession = Depends(session_scope),
) -> PublicMessage:
    """Revoke every active session and record who initiated the action."""

    now = SystemClock().now()
    await session.get(Account, account_id, with_for_update=True)
    records = await session.scalars(
        select(Session).where(Session.account_id == account_id, Session.revoked_at.is_(None))
    )
    for record in records:
        record.revoked_at = now
    session.add(
        SecurityEvent(
            actor_id=admin.id,
            event_type="admin_session_revocation",
            outcome="accepted",
            metadata_json={"account_id": str(account_id)},
            created_at=now,
        )
    )
    await session.commit()
    return PublicMessage(message="Active sessions revoked.")


@router.get("/couples", response_model=AdminCollectionResponse)
async def couples(
    _admin: Account = Depends(current_admin),
    session: AsyncSession = Depends(session_scope),
) -> AdminCollectionResponse:
    """List relationship container metadata without member content."""

    records = (await session.execute(
        select(
            Couple.id,
            Couple.created_at,
            Couple.ended_at,
            func.count(CoupleMember.id),
        )
        .outerjoin(CoupleMember, CoupleMember.couple_id == Couple.id)
        .group_by(Couple.id)
        .order_by(Couple.created_at.desc())
        .limit(100)
    )).all()
    return AdminCollectionResponse(
        items=[
            {
                "id": str(item.id),
                "created_at": item.created_at,
                "ended_at": item.ended_at,
                "member_count": item[3],
            }
            for item in records
        ]
    )


@router.get("/question-batches", response_model=AdminCollectionResponse)
async def question_batches(
    _admin: Account = Depends(current_admin),
    session: AsyncSession = Depends(session_scope),
) -> AdminCollectionResponse:
    """Expose global generation provenance and validation reasons."""

    records = list(
        await session.scalars(
            select(GenerationBatch).order_by(GenerationBatch.publish_date.desc()).limit(30)
        )
    )
    return AdminCollectionResponse(
        items=[
            {
                "id": str(item.id),
                "publish_date": item.publish_date,
                "model": item.model,
                "model_digest": item.model_digest,
                "prompt_version": item.prompt_version,
                "parameters": item.parameters,
                "validation_results": item.validation_results,
                "candidate_snapshot": item.candidate_snapshot,
                "selected_count": len(item.selected_question_ids),
                "fallback_reason": item.fallback_reason,
                "duration_ms": item.duration_ms,
                "created_at": item.created_at,
            }
            for item in records
        ]
    )


@router.post("/question-batches/{publish_date}/regenerate", response_model=PublicMessage)
async def regenerate_batch(
    publish_date: date,
    _admin: Account = Depends(current_admin),
    session: AsyncSession = Depends(session_scope),
) -> PublicMessage:
    """Remove an unanswered future global pool so the worker regenerates it."""

    if publish_date <= date.today():
        raise HTTPException(status.HTTP_409_CONFLICT, "Only future pools can be regenerated")
    global_ids = select(Question.id).where(
        Question.publish_date == publish_date,
        Question.couple_id.is_(None),
    )
    if await _row_count(session, QuizAnswer, QuizAnswer.question_id.in_(global_ids)):
        raise HTTPException(status.HTTP_409_CONFLICT, "Answered questions cannot be regenerated")
    if await _row_count(session, QuizDayQuestion, QuizDayQuestion.question_id.in_(global_ids)):
        raise HTTPException(status.HTTP_409_CONFLICT, "Materialized questions cannot be regenerated")
    await session.execute(delete(Question).where(Question.id.in_(global_ids)))
    await session.execute(
        delete(GenerationBatch).where(GenerationBatch.publish_date == publish_date)
    )
    await session.commit()
    return PublicMessage(message="Question pool queued for regeneration.")


@router.get("/question-reports", response_model=AdminCollectionResponse)
async def question_reports(
    _admin: Account = Depends(current_admin),
    session: AsyncSession = Depends(session_scope),
) -> AdminCollectionResponse:
    """List report reasons while masking couple-authored prompt text."""

    records = (await session.execute(
        select(QuestionReport, Question)
        .join(Question, Question.id == QuestionReport.question_id)
        .where(QuestionReport.resolved_at.is_(None))
        .order_by(QuestionReport.created_at)
        .limit(100)
    )).all()
    return AdminCollectionResponse(
        items=[
            {
                "report_id": str(report.id),
                "question_id": str(question.id),
                "prompt": question.prompt if question.couple_id is None else "[couple-created]",
                "source": question.source,
                "reason": report.reason if question.couple_id is None else "private custom report",
                "created_at": report.created_at,
            }
            for report, question in records
        ]
    )


@router.post("/question-reports/{report_id}/resolve", response_model=PublicMessage)
async def resolve_question_report(
    report_id: UUID,
    payload: AdminQuestionAction,
    admin: Account = Depends(current_admin),
    session: AsyncSession = Depends(session_scope),
) -> PublicMessage:
    """Resolve one report and optionally disable its question."""

    report = await session.get(QuestionReport, report_id, with_for_update=True)
    if report is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Report is unavailable")
    now = SystemClock().now()
    report.resolved_at = now
    if payload.disable_question:
        question = await session.get(Question, report.question_id, with_for_update=True)
        if question:
            question.disabled_at = now
    session.add(
        SecurityEvent(
            actor_id=admin.id,
            event_type="question_report_resolution",
            outcome="disabled" if payload.disable_question else "resolved",
            metadata_json={"report_id": str(report.id)},
            created_at=now,
        )
    )
    await session.commit()
    return PublicMessage(message="Question report resolved.")


def _curated_input(record: CuratedBankQuestion) -> CuratedQuestionInput:
    return CuratedQuestionInput.model_validate(
        {
            "stable_key": record.stable_key,
            "kind": record.kind,
            "prompt": record.prompt,
            "category": record.category,
            "intimacy": record.intimacy,
            "options": record.options,
            "option_icons": record.option_icons,
            "scale_low_label": record.scale_low_label,
            "scale_high_label": record.scale_high_label,
            "enabled": record.enabled,
        }
    )


@router.get("/curated-bank", response_model=list[CuratedQuestionInput])
async def curated_bank(
    _admin: Account = Depends(current_admin),
    session: AsyncSession = Depends(session_scope),
) -> list[CuratedQuestionInput]:
    """Export the editable bank, falling back to the reviewed repository bank."""

    records = list(
        await session.scalars(
            select(CuratedBankQuestion).order_by(CuratedBankQuestion.stable_key)
        )
    )
    if records:
        return [_curated_input(item) for item in records]
    return [
        CuratedQuestionInput(
            **item.model_dump(exclude={"client_id"}),
            stable_key=item.client_id,
        )
        for item in load_curated_bank()
    ]


@router.put("/curated-bank", response_model=PublicMessage)
async def replace_curated_bank(
    payload: CuratedImportRequest,
    admin: Account = Depends(current_admin),
    session: AsyncSession = Depends(session_scope),
) -> PublicMessage:
    """Validate and atomically replace the owner-managed fallback bank."""

    validated = [
        CandidateQuestion(
            client_id=item.stable_key,
            kind=QuestionKind(item.kind),
            prompt=item.prompt,
            category=Category(item.category),
            intimacy=item.intimacy,
            options=item.options,
            option_icons=[IconKey(icon) for icon in item.option_icons],
            scale_low_label=item.scale_low_label,
            scale_high_label=item.scale_high_label,
        )
        for item in payload.questions
    ]
    if len({item.client_id for item in validated}) != len(validated):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Stable keys must be unique")
    if sum(not item.intimacy for item in validated) < 5 or not any(
        item.intimacy for item in validated
    ):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Bank coverage is incomplete")
    await session.execute(delete(CuratedBankQuestion))
    now = SystemClock().now()
    session.add_all(
        [
            CuratedBankQuestion(
                stable_key=item.stable_key,
                kind=item.kind,
                prompt=item.prompt,
                category=item.category,
                intimacy=item.intimacy,
                options=item.options,
                option_icons=item.option_icons,
                scale_low_label=item.scale_low_label,
                scale_high_label=item.scale_high_label,
                enabled=item.enabled,
                updated_by=admin.id,
                created_at=now,
                updated_at=now,
            )
            for item in payload.questions
        ]
    )
    await session.commit()
    return PublicMessage(message="Curated bank replaced.")


@router.put("/registration", response_model=PublicMessage)
async def registration_control(
    payload: AdminRegistrationControl,
    admin: Account = Depends(current_admin),
    session: AsyncSession = Depends(session_scope),
) -> PublicMessage:
    """Pause or resume registration without touching deployment secrets."""

    record = await session.get(RuntimeSetting, "registration", with_for_update=True)
    now = SystemClock().now()
    if record is None:
        record = RuntimeSetting(
            key="registration",
            value_json={"enabled": payload.enabled},
            updated_at=now,
            updated_by=admin.id,
        )
        session.add(record)
    else:
        record.value_json = {"enabled": payload.enabled}
        record.updated_at = now
        record.updated_by = admin.id
    await session.commit()
    return PublicMessage(message="Registration setting updated.")


@router.put("/releases/{version}", response_model=PublicMessage)
async def publish_release(
    version: str,
    payload: ApkReleaseInput,
    admin: Account = Depends(current_admin),
    session: AsyncSession = Depends(session_scope),
) -> PublicMessage:
    """Create or update signed GitHub-hosted APK metadata."""

    if version != payload.version:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Version path and body differ")
    try:
        await upsert_apk_release(session, payload, admin.id)
    except PublishedReleaseImmutable as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc)) from exc
    await session.commit()
    return PublicMessage(message="Release metadata updated.")


@router.get("/security-events", response_model=AdminCollectionResponse)
async def security_events(
    _admin: Account = Depends(current_admin),
    session: AsyncSession = Depends(session_scope),
) -> AdminCollectionResponse:
    """Return bounded privacy-safe security audit events."""

    records = list(
        await session.scalars(
            select(SecurityEvent).order_by(SecurityEvent.created_at.desc()).limit(100)
        )
    )
    return AdminCollectionResponse(
        items=[
            {
                "id": str(item.id),
                "actor_id": str(item.actor_id) if item.actor_id else None,
                "event_type": item.event_type,
                "outcome": item.outcome,
                "metadata": item.metadata_json,
                "created_at": item.created_at,
            }
            for item in records
        ]
    )
