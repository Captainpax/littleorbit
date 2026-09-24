"""Typed Big Orbit job execution and content-free alert synthesis."""

from datetime import timedelta

from little_orbit_ai.ollama import OllamaClient
from sqlalchemy import and_, delete, or_, select

from .admin_device_models import (
    AdminAlert,
    AdminAlertDelivery,
    AdminJobRequest,
    BackupRun,
)
from .clock import SystemClock
from .database import SessionFactory
from .models import Question, QuestionReport
from .quiz_learning_service import learn_feedback_week
from .quiz_observatory_service import quiz_health_flags


async def process_quiz_admin_jobs(
    client: OllamaClient,
    generate_week,
) -> int:
    """Claim and execute allowlisted quiz jobs; host backup jobs remain separate."""

    jobs = await _claim_quiz_jobs()
    for job in jobs:
        try:
            if job.target_week is None:
                raise RuntimeError("quiz job target week is missing")
            if job.kind == "learn_quizzes":
                outcome = await learn_feedback_week(job.target_week, client)
                result: dict[str, object] = {"outcome": outcome}
            else:
                result = dict(
                    await generate_week(
                        job.target_week, force=job.kind == "regenerate_quizzes"
                    )
                )
            await _finish_job(job.id, "passed", result)
        except Exception:
            await _finish_job(job.id, "failed", {"reason": "job_failed"})
            await upsert_admin_alert(
                f"admin-job:{job.id}",
                "admin_job_failed",
                "warning",
                "An operations job needs attention",
                f"The allowlisted {job.kind} job failed. Open Operations to retry.",
                "/operations",
            )
    return len(jobs)


async def refresh_admin_alerts() -> None:
    """Create deduplicated operational alerts without relationship content."""

    now = SystemClock().now()
    async with SessionFactory() as session:
        report = await session.scalar(
            select(QuestionReport.id)
            .join(Question, Question.id == QuestionReport.question_id)
            .where(QuestionReport.resolved_at.is_(None), Question.couple_id.is_(None))
            .limit(1)
        )
        backup = await session.scalar(
            select(BackupRun)
            .where(BackupRun.kind == "backup", BackupRun.status == "passed")
            .order_by(BackupRun.created_at.desc())
            .limit(1)
        )
    await _set_admin_alert_condition(
        report is not None,
        "question-report:open",
        "question_report",
        "warning",
        "A global question was reported",
        "Review the safety reason and either resolve or disable the question.",
        "/questions/reports",
    )
    await _set_admin_alert_condition(
        backup is None or backup.created_at < now - timedelta(hours=26),
        "backup:stale",
        "backup_stale",
        "critical",
        "Encrypted backup is overdue",
        "No successful encrypted backup was recorded in the last 26 hours.",
        "/operations/backups",
    )
    await _refresh_quiz_alerts()


async def _refresh_quiz_alerts() -> None:
    flags = await quiz_health_flags()
    definitions = (
        (
            "reserve_low",
            "quiz-reserve:low",
            "quiz_reserve_low",
            "critical",
            "Quiz reserve needs replenishment",
            "Fewer than seven offline quiz days remain in the reviewed reserve.",
        ),
        (
            "context_unavailable",
            "quiz-context:unavailable",
            "quiz_context_unavailable",
            "warning",
            "Quiz public context is using safe fallback",
            "At least one allowlisted source has no valid thirty-day snapshot.",
        ),
        (
            "latest_run_degraded",
            "quiz-run:degraded",
            "quiz_run_degraded",
            "warning",
            "The latest quiz intelligence run degraded",
            "Review provenance before retrying the allowlisted operation.",
        ),
    )
    for key, dedupe, kind, severity, title, summary in definitions:
        await _set_admin_alert_condition(
            flags[key], dedupe, kind, severity, title, summary, "/ai/observatory"
        )


async def upsert_admin_alert(
    dedupe_key: str,
    kind: str,
    severity: str,
    title: str,
    summary: str,
    action_path: str | None,
) -> None:
    """Create or refresh one deterministic, content-free alert."""

    await _set_admin_alert_condition(
        True, dedupe_key, kind, severity, title, summary, action_path
    )


async def _set_admin_alert_condition(
    active: bool,
    dedupe_key: str,
    kind: str,
    severity: str,
    title: str,
    summary: str,
    action_path: str | None,
) -> None:
    """Open, resolve, or safely reopen one deterministic alert condition."""

    now = SystemClock().now()
    async with SessionFactory() as session:
        record = await session.scalar(
            select(AdminAlert).where(AdminAlert.dedupe_key == dedupe_key).with_for_update()
        )
        if not active:
            if record is not None and record.resolved_at is None:
                record.resolved_at = now
        elif record is None:
            session.add(
                AdminAlert(
                    dedupe_key=dedupe_key,
                    kind=kind,
                    severity=severity,
                    title=title,
                    summary=summary,
                    action_path=action_path,
                    created_at=now,
                )
            )
        else:
            reopened = record.resolved_at is not None
            record.kind = kind
            record.severity = severity
            record.title = title
            record.summary = summary
            record.action_path = action_path
            record.resolved_at = None
            if reopened:
                await session.execute(
                    delete(AdminAlertDelivery).where(
                        AdminAlertDelivery.alert_id == record.id
                    )
                )
        await session.commit()


async def _claim_quiz_jobs() -> list[AdminJobRequest]:
    now = SystemClock().now()
    stale = now - timedelta(hours=2)
    async with SessionFactory() as session:
        records = list(
            await session.scalars(
                select(AdminJobRequest)
                .where(
                    AdminJobRequest.kind.in_(
                        ("learn_quizzes", "generate_quizzes", "regenerate_quizzes")
                    ),
                    or_(
                        AdminJobRequest.status == "pending",
                        and_(
                            AdminJobRequest.status == "running",
                            or_(
                                AdminJobRequest.started_at.is_(None),
                                AdminJobRequest.started_at <= stale,
                            ),
                        ),
                    ),
                )
                .order_by(AdminJobRequest.created_at)
                .limit(5)
                .with_for_update(skip_locked=True)
            )
        )
        for record in records:
            record.status = "running"
            record.started_at = now
            record.finished_at = None
            record.result_json = {}
        await session.commit()
        for record in records:
            session.expunge(record)
    return records


async def _finish_job(
    job_id,
    status: str,
    result: dict[str, object],
) -> None:
    async with SessionFactory() as session:
        record = await session.get(AdminJobRequest, job_id, with_for_update=True)
        if record is None:
            return
        record.status = status
        record.result_json = result
        record.finished_at = SystemClock().now()
        await session.commit()
