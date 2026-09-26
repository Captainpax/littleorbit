"""Privacy-limited action inbox, quiz intelligence, and typed operations API."""

from datetime import UTC, datetime, time, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..admin_device_models import (
    AdminAlert,
    AdminAlertDelivery,
    AdminJobRequest,
    BackupRun,
)
from ..big_orbit_dependencies import BigOrbitPrincipal, current_big_orbit_admin
from ..big_orbit_schemas import (
    AdminAlertAck,
    AdminAlertView,
    AdminJobMutation,
    AdminJobView,
)
from ..clock import SystemClock
from ..config import Settings, get_settings
from ..database import session_scope
from ..models import Question, QuestionReport
from ..quiz_intelligence_models import (
    AnonymousQuestionReview,
    FeedbackWeeklyAggregate,
    QuestionFeedback,
    WebContextSource,
)
from ..quiz_observatory_service import observatory_items
from ..quiz_v3_schemas import QuizFeedbackAggregateView
from ..schemas import AdminCollectionResponse, PublicMessage

router = APIRouter(prefix="/v2/admin", tags=["big-orbit-console"])


@router.get("/action-inbox", response_model=AdminCollectionResponse)
async def action_inbox(
    principal: BigOrbitPrincipal = Depends(current_big_orbit_admin),
    session: AsyncSession = Depends(session_scope),
) -> AdminCollectionResponse:
    """Combine unread operational alerts, global reports, and queued jobs."""

    alerts = await _alert_views(session, principal, acknowledged=False)
    reports = list(
        (
            await session.execute(
                select(QuestionReport, Question)
                .join(Question, Question.id == QuestionReport.question_id)
                .where(
                    QuestionReport.resolved_at.is_(None),
                    Question.couple_id.is_(None),
                )
                .order_by(QuestionReport.created_at)
                .limit(50)
            )
        ).all()
    )
    jobs = list(
        await session.scalars(
            select(AdminJobRequest)
            .where(AdminJobRequest.status.in_(("pending", "running", "failed")))
            .order_by(AdminJobRequest.created_at.desc())
            .limit(30)
        )
    )
    items: list[dict[str, object]] = [
        {"type": "alert", **item.model_dump(mode="json")} for item in alerts
    ]
    items.extend(
        {
            "type": "question_report",
            "id": str(report.id),
            "question_id": str(question.id),
            "prompt": question.prompt,
            "reason": report.reason,
            "created_at": report.created_at,
        }
        for report, question in reports
    )
    items.extend(
        {
            "type": "job",
            "id": str(job.id),
            "kind": job.kind,
            "status": job.status,
            "created_at": job.created_at,
        }
        for job in jobs
    )
    return AdminCollectionResponse(items=items)


@router.get("/alerts", response_model=list[AdminAlertView])
async def alerts(
    acknowledged: bool = False,
    principal: BigOrbitPrincipal = Depends(current_big_orbit_admin),
    session: AsyncSession = Depends(session_scope),
) -> list[AdminAlertView]:
    """Return content-free operational alerts for only the current device."""

    return await _alert_views(session, principal, acknowledged)


@router.post("/alerts/acknowledge", response_model=PublicMessage)
async def acknowledge_alerts(
    payload: AdminAlertAck,
    principal: BigOrbitPrincipal = Depends(current_big_orbit_admin),
    session: AsyncSession = Depends(session_scope),
) -> PublicMessage:
    """Acknowledge alerts independently for this Big Orbit installation."""

    now = SystemClock().now()
    deliveries = list(
        await session.scalars(
            select(AdminAlertDelivery)
            .where(
                AdminAlertDelivery.device_id == principal.device.id,
                AdminAlertDelivery.alert_id.in_(payload.alert_ids),
            )
            .with_for_update()
        )
    )
    found = {item.alert_id for item in deliveries}
    existing = set(
        await session.scalars(select(AdminAlert.id).where(AdminAlert.id.in_(payload.alert_ids)))
    )
    for delivery in deliveries:
        delivery.acknowledged_at = now
    session.add_all(
        [
            AdminAlertDelivery(
                alert_id=alert_id,
                device_id=principal.device.id,
                acknowledged_at=now,
                created_at=now,
            )
            for alert_id in existing - found
        ]
    )
    await session.commit()
    return PublicMessage(message="Action inbox updated.")


@router.get(
    "/quiz-intelligence",
    response_model=list[QuizFeedbackAggregateView],
)
async def quiz_intelligence(
    weeks: int = Query(default=8, ge=1, le=52),
    _principal: BigOrbitPrincipal = Depends(current_big_orbit_admin),
    session: AsyncSession = Depends(session_scope),
) -> list[QuizFeedbackAggregateView]:
    """Expose only K-anonymous global-question feedback and sanitized reviews."""

    cutoff = SystemClock().now().date() - timedelta(weeks=weeks)
    rows = list(
        (
            await session.execute(
                select(FeedbackWeeklyAggregate, Question)
                .join(Question, Question.id == FeedbackWeeklyAggregate.question_id)
                .where(
                    FeedbackWeeklyAggregate.week_start >= cutoff,
                    FeedbackWeeklyAggregate.distinct_accounts >= 5,
                    Question.couple_id.is_(None),
                )
                .order_by(FeedbackWeeklyAggregate.week_start.desc())
                .limit(250)
            )
        ).all()
    )
    result: list[QuizFeedbackAggregateView] = []
    for aggregate, question in rows:
        reviews = await _aggregate_reviews(session, aggregate)
        result.append(
            QuizFeedbackAggregateView.model_validate(
                {
                    "question_id": question.id,
                    "prompt": question.prompt,
                    "category": question.category,
                    "intimacy": question.intimacy,
                    "rating_count": aggregate.rating_count,
                    "average_stars": aggregate.score_sum / aggregate.rating_count,
                    "tag_counts": aggregate.tag_counts,
                    "sanitized_reviews": reviews,
                    "week_start": aggregate.week_start,
                }
            )
        )
    return result


@router.get("/ai/observatory", response_model=AdminCollectionResponse)
async def ai_observatory(
    _principal: BigOrbitPrincipal = Depends(current_big_orbit_admin),
    settings: Settings = Depends(get_settings),
) -> AdminCollectionResponse:
    """Return model provenance and job health without model inputs or user data."""

    return AdminCollectionResponse(items=await observatory_items(settings))


@router.post("/jobs", response_model=AdminJobView)
async def request_job(
    payload: AdminJobMutation,
    principal: BigOrbitPrincipal = Depends(current_big_orbit_admin),
    session: AsyncSession = Depends(session_scope),
) -> AdminJobView:
    """Queue only a known operation; arbitrary commands and SQL are impossible."""

    existing = await session.scalar(
        select(AdminJobRequest).where(
            AdminJobRequest.requested_by == principal.account.id,
            AdminJobRequest.operation_id == payload.operation_id,
        )
    )
    if existing is not None:
        if existing.kind != payload.kind or existing.target_week != payload.target_week:
            raise HTTPException(status.HTTP_409_CONFLICT, "Operation ID was already used")
        return _job_view(existing)
    _validate_job(payload)
    record = AdminJobRequest(
        operation_id=payload.operation_id,
        kind=payload.kind,
        requested_by=principal.account.id,
        requested_device_id=principal.device.id,
        target_week=payload.target_week,
        status="pending",
        result_json={},
        created_at=SystemClock().now(),
    )
    session.add(record)
    await session.commit()
    await session.refresh(record)
    return _job_view(record)


@router.get("/jobs", response_model=list[AdminJobView])
async def jobs(
    _principal: BigOrbitPrincipal = Depends(current_big_orbit_admin),
    session: AsyncSession = Depends(session_scope),
) -> list[AdminJobView]:
    records = list(
        await session.scalars(
            select(AdminJobRequest).order_by(AdminJobRequest.created_at.desc()).limit(100)
        )
    )
    return [_job_view(item) for item in records]


@router.get("/backups", response_model=AdminCollectionResponse)
async def backups(
    _principal: BigOrbitPrincipal = Depends(current_big_orbit_admin),
    session: AsyncSession = Depends(session_scope),
) -> AdminCollectionResponse:
    records = list(
        await session.scalars(select(BackupRun).order_by(BackupRun.created_at.desc()).limit(60))
    )
    return AdminCollectionResponse(
        items=[
            {
                "id": str(item.id),
                "kind": item.kind,
                "status": item.status,
                "destination": item.destination,
                "manifest_sha256": item.manifest_sha256,
                "details": item.details_json,
                "created_at": item.created_at,
                "finished_at": item.finished_at,
            }
            for item in records
        ]
    )


@router.get("/web-context-sources", response_model=AdminCollectionResponse)
async def web_context_sources(
    _principal: BigOrbitPrincipal = Depends(current_big_orbit_admin),
    session: AsyncSession = Depends(session_scope),
) -> AdminCollectionResponse:
    records = list(
        await session.scalars(select(WebContextSource).order_by(WebContextSource.hostname))
    )
    return AdminCollectionResponse(
        items=[
            {
                "id": str(item.id),
                "base_url": item.base_url,
                "hostname": item.hostname,
                "code_owned": item.code_owned,
                "enabled": item.enabled,
                "created_at": item.created_at,
            }
            for item in records
        ]
    )


async def _alert_views(
    session: AsyncSession,
    principal: BigOrbitPrincipal,
    acknowledged: bool,
) -> list[AdminAlertView]:
    rows = list(
        (
            await session.execute(
                select(AdminAlert, AdminAlertDelivery)
                .outerjoin(
                    AdminAlertDelivery,
                    (AdminAlertDelivery.alert_id == AdminAlert.id)
                    & (AdminAlertDelivery.device_id == principal.device.id),
                )
                .where(AdminAlert.resolved_at.is_(None))
                .order_by(AdminAlert.created_at.desc())
                .limit(100)
            )
        ).all()
    )
    result = []
    for alert, delivery in rows:
        was_acknowledged = bool(delivery and delivery.acknowledged_at)
        if was_acknowledged != acknowledged:
            continue
        result.append(
            AdminAlertView(
                id=alert.id,
                kind=alert.kind,
                severity=alert.severity,
                title=alert.title,
                summary=alert.summary,
                action_path=alert.action_path,
                created_at=alert.created_at,
                acknowledged=was_acknowledged,
            )
        )
    return result


async def _aggregate_reviews(
    session: AsyncSession,
    aggregate: FeedbackWeeklyAggregate,
) -> list[str]:
    start = datetime.combine(aggregate.week_start, time.min, tzinfo=UTC)
    end = start + timedelta(days=7)
    linked = list(
        await session.scalars(
            select(QuestionFeedback.sanitized_review).where(
                QuestionFeedback.question_id == aggregate.question_id,
                QuestionFeedback.updated_at >= start,
                QuestionFeedback.updated_at < end,
                QuestionFeedback.review_status == "accepted",
                QuestionFeedback.sanitized_review.is_not(None),
            )
        )
    )
    anonymous = list(
        await session.scalars(
            select(AnonymousQuestionReview.sanitized_review).where(
                AnonymousQuestionReview.question_id == aggregate.question_id,
                AnonymousQuestionReview.week_start == aggregate.week_start,
                AnonymousQuestionReview.sanitized_review.is_not(None),
            )
        )
    )
    return [item for item in [*linked, *anonymous] if item][:20]


def _validate_job(payload: AdminJobMutation) -> None:
    needs_week = payload.kind in {
        "learn_quizzes",
        "generate_quizzes",
        "regenerate_quizzes",
    }
    if needs_week != (payload.target_week is not None):
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            "Quiz jobs require one Monday target week; backup jobs do not",
        )
    if payload.target_week and payload.target_week.weekday() != 0:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Target week must be Monday")


def _job_view(record: AdminJobRequest) -> AdminJobView:
    return AdminJobView(
        id=record.id,
        kind=record.kind,
        target_week=record.target_week,
        status=record.status,
        result=record.result_json,
        created_at=record.created_at,
        started_at=record.started_at,
        finished_at=record.finished_at,
    )
