"""Revisioned and retry-safe mutations for daily quiz state."""

from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from .clock import SystemClock
from .models import Question, QuizDay, QuizDayMember, QuizDayQuestion, QuizDraft
from .quiz_v2_service import (
    date_is_editable,
    operation_exists,
    record_operation,
    validate_answer,
)
from .schemas import QuizDayMutation, QuizDraftMutation


async def save_draft(
    session: AsyncSession,
    day: QuizDay,
    actor_id: UUID,
    question_id: UUID,
    payload: QuizDraftMutation,
) -> None:
    """Create or revise one private answer while the daily set is editable."""

    if await operation_exists(session, day.couple_id, actor_id, payload.operation_id):
        return
    await _require_editable_member(session, day, actor_id)
    question = await session.scalar(
        select(Question)
        .join(QuizDayQuestion, QuizDayQuestion.question_id == Question.id)
        .where(
            QuizDayQuestion.quiz_day_id == day.id,
            QuizDayQuestion.question_id == question_id,
        )
    )
    if question is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Question is unavailable")
    answer = validate_answer(question, payload.answer)
    draft = await session.scalar(
        select(QuizDraft)
        .where(
            QuizDraft.quiz_day_id == day.id,
            QuizDraft.question_id == question_id,
            QuizDraft.account_id == actor_id,
        )
        .with_for_update()
    )
    revision = draft.revision if draft else 0
    if revision != payload.expected_revision:
        raise HTTPException(status.HTTP_409_CONFLICT, "Answer draft changed; refresh and retry")
    now = SystemClock().now()
    if draft is None:
        session.add(
            QuizDraft(
                quiz_day_id=day.id,
                question_id=question_id,
                account_id=actor_id,
                answer=answer,
                revision=1,
                updated_at=now,
            )
        )
    else:
        draft.answer = answer
        draft.revision += 1
        draft.updated_at = now
    day.revision += 1
    record_operation(session, day.couple_id, actor_id, payload.operation_id, "draft", day.quiz_date)


async def finish_day(
    session: AsyncSession, day: QuizDay, actor_id: UUID, payload: QuizDayMutation
) -> None:
    """Mark one member finished and reveal atomically when both are finished."""

    if await operation_exists(session, day.couple_id, actor_id, payload.operation_id):
        return
    state = await _require_editable_member(session, day, actor_id)
    _require_day_revision(day, payload.expected_day_revision)
    count = await session.scalar(
        select(func.count()).select_from(QuizDraft).where(
            QuizDraft.quiz_day_id == day.id, QuizDraft.account_id == actor_id
        )
    )
    if count != 5:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Answer all five questions")
    state.completed_at = SystemClock().now()
    await session.flush()
    incomplete = await session.scalar(
        select(func.count()).select_from(QuizDayMember).where(
            QuizDayMember.quiz_day_id == day.id,
            QuizDayMember.completed_at.is_(None),
        )
    )
    if incomplete == 0:
        day.revealed_at = SystemClock().now()
    day.revision += 1
    record_operation(session, day.couple_id, actor_id, payload.operation_id, "finish", day.quiz_date)


async def reopen_day(
    session: AsyncSession, day: QuizDay, actor_id: UUID, payload: QuizDayMutation
) -> None:
    """Clear the caller's finish marker while shared reveal is still pending."""

    if await operation_exists(session, day.couple_id, actor_id, payload.operation_id):
        return
    state = await _require_editable_member(session, day, actor_id, allow_finished=True)
    _require_day_revision(day, payload.expected_day_revision)
    state.completed_at = None
    day.revision += 1
    record_operation(session, day.couple_id, actor_id, payload.operation_id, "reopen", day.quiz_date)


async def _require_editable_member(
    session: AsyncSession, day: QuizDay, actor_id: UUID, allow_finished: bool = False
) -> QuizDayMember:
    if day.revealed_at is not None or not date_is_editable(day.quiz_date):
        raise HTTPException(status.HTTP_409_CONFLICT, "Quiz day is no longer editable")
    state = await session.scalar(
        select(QuizDayMember)
        .where(QuizDayMember.quiz_day_id == day.id, QuizDayMember.account_id == actor_id)
        .with_for_update()
    )
    if state is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Quiz day is unavailable")
    if state.completed_at is not None and not allow_finished:
        raise HTTPException(status.HTTP_409_CONFLICT, "Reopen the quiz before editing")
    return state


def _require_day_revision(day: QuizDay, expected: int) -> None:
    if day.revision != expected:
        raise HTTPException(status.HTTP_409_CONFLICT, "Quiz day changed; refresh and retry")
