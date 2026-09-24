"""Plan and persist one privacy-safe thematic arc for each upcoming quiz week."""

import hashlib
import json
from dataclasses import dataclass
from datetime import date, timedelta
from uuid import UUID

from little_orbit_ai.ollama import OllamaClient, OllamaFailure
from little_orbit_ai.prompt import build_week_plan_prompt
from little_orbit_ai.schemas import DayTheme, LearningPolicy, WeeklyThemePlan
from sqlalchemy import select, text

from .clock import SystemClock
from .database import SessionFactory
from .quiz_intelligence_models import AiPolicyVersion, QuizDayTheme, QuizWeekPlan


@dataclass(frozen=True)
class StoredDayTheme:
    """Prompt and public-display theme metadata for one exact local date."""

    id: UUID
    weekly_title: str
    weekly_summary: str
    day: DayTheme


async def plan_quiz_week(
    week_start: date,
    client: OllamaClient,
    policy: LearningPolicy | None,
    public_context: list[str],
    knowledge: list[str],
    *,
    timezone: str,
    locale: str,
) -> str:
    """Create exactly one validated plan, falling back without weakening its shape."""

    if week_start.weekday() != 0:
        raise ValueError("quiz week must start on Monday")
    if await _plan_exists(week_start):
        return "already_planned"
    prompt = build_week_plan_prompt(week_start, policy, public_context, knowledge, locale)
    try:
        plan = await client.plan_week(prompt)
        outcome = "model"
    except OllamaFailure:
        plan = _fallback_plan(week_start)
        outcome = "fallback"
    digest = _source_digest(policy, public_context, knowledge)
    await _persist_plan(plan, timezone, locale, digest)
    return outcome


async def theme_for_date(target: date) -> StoredDayTheme | None:
    """Return one public theme without exposing generation or feedback content."""

    async with SessionFactory() as session:
        row = (
            await session.execute(
                select(QuizDayTheme, QuizWeekPlan)
                .join(QuizWeekPlan, QuizWeekPlan.id == QuizDayTheme.week_plan_id)
                .where(QuizDayTheme.local_date == target)
            )
        ).one_or_none()
    if row is None:
        return None
    day, week = row
    return StoredDayTheme(
        day.id,
        week.arc_title,
        week.arc_summary,
        DayTheme(
            date=day.local_date,
            title=day.title,
            summary=day.summary,
            observance=day.observance,
        ),
    )


async def quiz_week_planned(week_start: date) -> bool:
    """Let the hourly worker avoid repeated browsing after Saturday succeeds."""

    return await _plan_exists(week_start)


async def mark_week_published(week_start: date) -> None:
    """Advance the plan only after all seven daily pools have safe coverage."""

    async with SessionFactory() as session:
        record = await session.scalar(
            select(QuizWeekPlan)
            .where(QuizWeekPlan.week_start == week_start)
            .with_for_update()
        )
        if record is not None:
            record.status = "published"
            await session.commit()


async def _plan_exists(week_start: date) -> bool:
    async with SessionFactory() as session:
        return (
            await session.scalar(
                select(QuizWeekPlan.id).where(QuizWeekPlan.week_start == week_start)
            )
            is not None
        )


async def _persist_plan(
    plan: WeeklyThemePlan, timezone: str, locale: str, source_digest: str
) -> None:
    now = SystemClock().now()
    async with SessionFactory() as session:
        await session.execute(text("SELECT pg_advisory_xact_lock(13002026)"))
        if await session.scalar(
            select(QuizWeekPlan.id).where(QuizWeekPlan.week_start == plan.week_start)
        ):
            return
        policy_version = await session.scalar(
            select(AiPolicyVersion.version)
            .where(AiPolicyVersion.status == "active")
            .order_by(AiPolicyVersion.version.desc())
            .limit(1)
        )
        week = QuizWeekPlan(
            week_start=plan.week_start,
            timezone=timezone,
            locale=locale,
            arc_title=plan.arc_title,
            arc_summary=plan.arc_summary,
            source_digest=source_digest,
            policy_version=policy_version,
            status="planned",
            created_at=now,
        )
        session.add(week)
        await session.flush()
        session.add_all(
            [
                QuizDayTheme(
                    week_plan_id=week.id,
                    local_date=item.date,
                    day_index=index,
                    title=item.title,
                    summary=item.summary,
                    observance=item.observance,
                    created_at=now,
                )
                for index, item in enumerate(plan.days)
            ]
        )
        await session.commit()


def _source_digest(
    policy: LearningPolicy | None, public_context: list[str], knowledge: list[str]
) -> str:
    payload = {
        "policy": policy.model_dump(mode="json") if policy else None,
        "context": public_context,
        "knowledge": knowledge,
    }
    return hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()


def _fallback_plan(week_start: date) -> WeeklyThemePlan:
    """Return a complete evergreen arc when local inference is unavailable."""

    themes = (
        ("Little joys", "Notice an ordinary detail that makes shared life warmer."),
        ("Stories we carry", "Revisit memories and the meanings that changed over time."),
        ("Curious futures", "Imagine possibilities without turning them into obligations."),
        ("Ways we show care", "Explore the small signals that help care feel recognizable."),
        ("Play and surprise", "Make room for humor, novelty, and low-pressure adventure."),
        ("Values in motion", "Reflect on choices that quietly express shared values."),
        ("Carry it forward", "Choose an insight or small idea worth bringing into next week."),
    )
    return WeeklyThemePlan(
        schema_version="1",
        week_start=week_start,
        arc_title="The small ways we choose each other",
        arc_summary="A week moving from everyday noticing toward meaningful shared intention.",
        days=[
            DayTheme(date=week_start + timedelta(days=index), title=title, summary=summary)
            for index, (title, summary) in enumerate(themes)
        ],
    )
