"""Content-free AI health and weekly-theme projections for Big Orbit."""

from datetime import date, timedelta

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from .clock import SystemClock
from .config import Settings
from .database import SessionFactory
from .models import GenerationBatch
from .quiz_intelligence_models import (
    AiKnowledgeChunk,
    AiPolicyVersion,
    AiRun,
    QuizDayTheme,
    QuizWeekPlan,
    WebContextSnapshot,
    WebContextSource,
)
from .quiz_reserve_service import reserve_health


async def observatory_items(settings: Settings) -> list[dict[str, object]]:
    """Describe provenance and capacity without returning prompts or user input."""

    now = SystemClock().now()
    reserve = await reserve_health()
    async with SessionFactory() as session:
        active = await session.scalar(
            select(AiPolicyVersion)
            .where(AiPolicyVersion.status == "active")
            .order_by(AiPolicyVersion.version.desc())
            .limit(1)
        )
        runs = list(
            await session.scalars(select(AiRun).order_by(AiRun.started_at.desc()).limit(30))
        )
        embedded = int(
            await session.scalar(
                select(func.count())
                .select_from(AiKnowledgeChunk)
                .where(AiKnowledgeChunk.active.is_(True))
            )
            or 0
        )
        upcoming = int(
            await session.scalar(
                select(func.count())
                .select_from(GenerationBatch)
                .where(GenerationBatch.publish_date >= now.date())
            )
            or 0
        )
        context = await _context_health(session)
        weeks = await _week_items(session, now.date() - timedelta(days=7))
    summary: dict[str, object] = {
        "type": "summary",
        "active_policy_version": active.version if active else None,
        "active_policy": active.policy_json if active else None,
        "schedule_timezone": settings.ai_schedule_timezone,
        "learning_local_hour": settings.ai_learning_local_hour,
        "generation_local_hour": settings.ai_generation_local_hour,
        "knowledge_chunks": embedded,
        "upcoming_days": upcoming,
        "reserve_general": reserve.general_available,
        "reserve_intimacy": reserve.intimacy_available,
        **context,
    }
    return [summary, *weeks, *_run_items(runs)]


def _run_items(runs: list[AiRun]) -> list[dict[str, object]]:
    """Serialize content-free run provenance for the owner console."""

    return [
        {
            "type": "run",
            "id": str(run.id),
            "run_key": run.run_key,
            "kind": run.kind,
            "status": run.status,
            "policy_version": run.policy_version,
            "summary": run.summary_json,
            "started_at": run.started_at,
            "finished_at": run.finished_at,
        }
        for run in runs
    ]


async def quiz_health_flags() -> dict[str, bool]:
    """Compute alert conditions using only counts, states, and timestamps."""

    now = SystemClock().now()
    reserve = await reserve_health()
    async with SessionFactory() as session:
        enabled_sources = int(
            await session.scalar(
                select(func.count())
                .select_from(WebContextSource)
                .where(
                    WebContextSource.enabled.is_(True),
                    WebContextSource.code_owned.is_(True),
                )
            )
            or 0
        )
        fresh_sources = int(
            await session.scalar(
                select(func.count(func.distinct(WebContextSnapshot.source_key))).where(
                    WebContextSnapshot.expires_at > now
                )
            )
            or 0
        )
        latest_run = await session.scalar(
            select(AiRun)
            .where(AiRun.kind.in_(("learning", "generation")))
            .order_by(AiRun.started_at.desc())
            .limit(1)
        )
    return {
        "reserve_low": reserve.general_available < 35 or reserve.intimacy_available < 7,
        "context_unavailable": enabled_sources > fresh_sources,
        "latest_run_degraded": bool(
            latest_run is not None and latest_run.status in {"failed", "fallback"}
        ),
    }


async def _context_health(session: AsyncSession) -> dict[str, object]:
    enabled = int(
        await session.scalar(
            select(func.count())
            .select_from(WebContextSource)
            .where(WebContextSource.enabled.is_(True), WebContextSource.code_owned.is_(True))
        )
        or 0
    )
    latest = await session.scalar(
        select(func.max(WebContextSnapshot.fetched_at)).select_from(WebContextSnapshot)
    )
    return {"context_sources": enabled, "context_last_fetched_at": latest}


async def _week_items(session: AsyncSession, cutoff: date) -> list[dict[str, object]]:
    weeks = list(
        await session.scalars(
            select(QuizWeekPlan)
            .where(QuizWeekPlan.week_start >= cutoff)
            .order_by(QuizWeekPlan.week_start)
            .limit(4)
        )
    )
    output: list[dict[str, object]] = []
    for week in weeks:
        days = list(
            await session.scalars(
                select(QuizDayTheme)
                .where(QuizDayTheme.week_plan_id == week.id)
                .order_by(QuizDayTheme.day_index)
            )
        )
        output.append(
            {
                "type": "week_plan",
                "week_start": week.week_start,
                "status": week.status,
                "arc_title": week.arc_title,
                "arc_summary": week.arc_summary,
                "days": [
                    {
                        "date": day.local_date,
                        "title": day.title,
                        "observance": day.observance,
                    }
                    for day in days
                ],
            }
        )
    return output
