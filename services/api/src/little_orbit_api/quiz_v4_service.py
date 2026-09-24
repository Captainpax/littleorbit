"""Attach public 1.3 theme metadata to already-authorized quiz responses."""

from datetime import date

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from .quiz_intelligence_models import (
    QuestionConcept,
    QuizDayTheme,
    QuizWeekPlan,
)
from .quiz_v3_schemas import QuizDayV3, QuizHistoryV3
from .quiz_v4_schemas import (
    QuizDayV4,
    QuizHistoryV4,
    QuizQuestionV4,
    QuizThemeView,
)


async def augment_day_v4(session: AsyncSession, source: QuizDayV3) -> QuizDayV4:
    """Add metadata only after the v3 service has authorized and redacted answers."""

    question_ids = [item.id for item in source.questions]
    concepts = {
        item.question_id: item
        for item in await session.scalars(
            select(QuestionConcept).where(QuestionConcept.question_id.in_(question_ids))
        )
    }
    questions = []
    for question in source.questions:
        concept = concepts.get(question.id)
        payload = question.model_dump(mode="python")
        if concept is not None:
            payload.update(
                depth=concept.depth,
                theme_role=concept.theme_role,
                theme_tags=concept.theme_tags,
            )
        questions.append(QuizQuestionV4.model_validate(payload))
    theme_view = await _theme_view(session, source.quiz_date)
    payload = source.model_dump(mode="python")
    payload.update(theme=theme_view, questions=questions)
    return QuizDayV4.model_validate(payload)


async def augment_history_v4(
    session: AsyncSession, items: list[QuizHistoryV3]
) -> list[QuizHistoryV4]:
    """Add only short theme labels to content-free history entries."""

    dates = [item.quiz_date for item in items]
    theme_rows = (
        await session.execute(
            select(QuizDayTheme.local_date, QuizDayTheme.title).where(
                QuizDayTheme.local_date.in_(dates)
            )
        )
    ).all()
    themes: dict[date, str] = {row[0]: row[1] for row in theme_rows}
    output: list[QuizHistoryV4] = []
    for item in items:
        payload = item.model_dump(mode="python")
        payload["daily_theme"] = themes.get(item.quiz_date)
        output.append(QuizHistoryV4.model_validate(payload))
    return output


async def _theme_view(session: AsyncSession, target: date) -> QuizThemeView | None:
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
    return QuizThemeView(
        weekly_title=week.arc_title,
        weekly_summary=week.arc_summary,
        daily_title=day.title,
        daily_summary=day.summary,
        observance=day.observance,
    )
