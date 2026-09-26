"""Shared reveal guard for legacy quiz data retained in exports and archives."""

from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from .models import QuizAnswer


async def revealed_legacy_answers(
    session: AsyncSession, couple_id: UUID
) -> list[QuizAnswer]:
    """Return answers only for questions submitted by both original participants."""

    revealed_questions = (
        select(QuizAnswer.question_id)
        .where(QuizAnswer.couple_id == couple_id)
        .group_by(QuizAnswer.question_id)
        .having(func.count(func.distinct(QuizAnswer.account_id)) >= 2)
    )
    return list(
        await session.scalars(
            select(QuizAnswer).where(
                QuizAnswer.couple_id == couple_id,
                QuizAnswer.question_id.in_(revealed_questions),
            )
        )
    )
