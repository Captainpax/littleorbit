"""Authorization-first private feedback and v3 response assembly."""

from datetime import date, datetime, timedelta
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from .clock import SystemClock
from .couple_access import lock_couple
from .models import CoupleMember, Question, QuizDay, QuizDayQuestion
from .quiz_intelligence_models import (
    QuestionFeedback,
    QuestionFeedbackOperation,
    QuizFeedbackRollout,
)
from .quiz_v2_schemas import QuizDayResponse, QuizHistoryItem
from .quiz_v3_schemas import (
    QuizDayV3,
    QuizFeedbackDelete,
    QuizFeedbackDeleteResult,
    QuizFeedbackMutation,
    QuizFeedbackView,
    QuizHistoryV3,
    QuizQuestionV3,
)
from .review_sanitizer import sanitize_review

FEEDBACK_DAYS = 30


async def put_feedback(
    session: AsyncSession,
    member: CoupleMember,
    actor_id: UUID,
    quiz_date: date,
    question_id: UUID,
    payload: QuizFeedbackMutation,
) -> QuizFeedbackView:
    """Create or edit feedback after couple authorization and shared reveal."""

    day, _, deadline = await _feedback_target(session, member, quiz_date, question_id)
    replay = await _operation(session, actor_id, payload.operation_id)
    if replay is not None:
        if replay.action != "put":
            raise HTTPException(status.HTTP_409_CONFLICT, "Operation ID was already used")
        return QuizFeedbackView.model_validate(replay.result_json)
    record = await session.scalar(
        select(QuestionFeedback)
        .where(
            QuestionFeedback.quiz_day_id == day.id,
            QuestionFeedback.question_id == question_id,
            QuestionFeedback.account_id == actor_id,
        )
        .with_for_update()
    )
    revision = record.revision if record else 0
    if revision != payload.expected_revision:
        raise HTTPException(status.HTTP_409_CONFLICT, "Feedback changed; refresh and retry")
    sanitized = sanitize_review(payload.review, payload.review_consent)
    now = SystemClock().now()
    if record is None:
        record = QuestionFeedback(
            quiz_day_id=day.id,
            question_id=question_id,
            couple_id=member.couple_id,
            account_id=actor_id,
            stars=payload.stars,
            tags=list(payload.tags),
            sanitized_review=sanitized.text,
            review_status=sanitized.status,
            revision=1,
            editable_until=deadline,
            created_at=now,
            updated_at=now,
        )
        session.add(record)
        await session.flush()
    else:
        record.stars = payload.stars
        record.tags = list(payload.tags)
        record.sanitized_review = sanitized.text
        record.review_status = sanitized.status
        record.revision += 1
        record.updated_at = now
    response = _feedback_view(record)
    _record_operation(session, actor_id, payload.operation_id, record.id, "put", response)
    return response


async def delete_feedback(
    session: AsyncSession,
    member: CoupleMember,
    actor_id: UUID,
    quiz_date: date,
    question_id: UUID,
    payload: QuizFeedbackDelete,
) -> QuizFeedbackDeleteResult:
    """Delete attributable feedback without exposing another account's record."""

    day, _, _ = await _feedback_target(session, member, quiz_date, question_id)
    replay = await _operation(session, actor_id, payload.operation_id)
    if replay is not None:
        if replay.action != "delete":
            raise HTTPException(status.HTTP_409_CONFLICT, "Operation ID was already used")
        return QuizFeedbackDeleteResult.model_validate(replay.result_json)
    record = await session.scalar(
        select(QuestionFeedback)
        .where(
            QuestionFeedback.quiz_day_id == day.id,
            QuestionFeedback.question_id == question_id,
            QuestionFeedback.account_id == actor_id,
        )
        .with_for_update()
    )
    if record is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Feedback is unavailable")
    if record.revision != payload.expected_revision:
        raise HTTPException(status.HTTP_409_CONFLICT, "Feedback changed; refresh and retry")
    await session.delete(record)
    result = QuizFeedbackDeleteResult()
    _record_operation(session, actor_id, payload.operation_id, None, "delete", result)
    return result


async def augment_day(
    session: AsyncSession,
    member: CoupleMember,
    actor_id: UUID,
    day: QuizDayResponse,
) -> QuizDayV3:
    """Attach only the caller's feedback to an otherwise v2-compatible response."""

    stored_day = await session.scalar(
        select(QuizDay).where(
            QuizDay.couple_id == member.couple_id,
            QuizDay.quiz_date == day.quiz_date,
        )
    )
    if stored_day is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Quiz day is unavailable")
    question_ids = [question.id for question in day.questions]
    global_ids = set(
        await session.scalars(
            select(Question.id).where(
                Question.id.in_(question_ids), Question.couple_id.is_(None)
            )
        )
    )
    feedback = {
        item.question_id: item
        for item in await session.scalars(
            select(QuestionFeedback).where(
                QuestionFeedback.quiz_day_id == stored_day.id,
                QuestionFeedback.account_id == actor_id,
            )
        )
    }
    rollout = await _rollout(session)
    deadline = (
        stored_day.revealed_at + timedelta(days=FEEDBACK_DAYS)
        if stored_day.revealed_at is not None
        else None
    )
    eligible_day = bool(
        stored_day.revealed_at
        and stored_day.revealed_at >= rollout
        and deadline
        and SystemClock().now() <= deadline
    )
    questions = []
    for question in day.questions:
        record = feedback.get(question.id)
        questions.append(
            QuizQuestionV3.model_validate(
                {
                    **question.model_dump(),
                    "feedback_eligible": eligible_day and question.id in global_ids,
                    "feedback_editable_until": deadline if question.id in global_ids else None,
                    "my_feedback": _feedback_view(record).model_dump() if record else None,
                }
            )
        )
    return QuizDayV3.model_validate({**day.model_dump(), "questions": questions})


async def augment_history(
    session: AsyncSession,
    member: CoupleMember,
    actor_id: UUID,
    items: list[QuizHistoryItem],
) -> list[QuizHistoryV3]:
    """Add private rating counts without exposing feedback or partner behavior."""

    result: list[QuizHistoryV3] = []
    for item in items:
        day_id = await session.scalar(
            select(QuizDay.id).where(
                QuizDay.couple_id == member.couple_id,
                QuizDay.quiz_date == item.quiz_date,
            )
        )
        count = 0
        if day_id is not None:
            count = int(
                await session.scalar(
                    select(func.count())
                    .select_from(QuestionFeedback)
                    .where(
                        QuestionFeedback.quiz_day_id == day_id,
                        QuestionFeedback.account_id == actor_id,
                    )
                )
                or 0
            )
        result.append(QuizHistoryV3.model_validate({**item.model_dump(), "rated_count": count}))
    return result


async def _feedback_target(
    session: AsyncSession,
    member: CoupleMember,
    quiz_date: date,
    question_id: UUID,
) -> tuple[QuizDay, Question, datetime]:
    await lock_couple(session, member.couple_id)
    day = await session.scalar(
        select(QuizDay)
        .where(QuizDay.couple_id == member.couple_id, QuizDay.quiz_date == quiz_date)
        .with_for_update()
    )
    if day is None or day.revealed_at is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Quiz feedback is unavailable")
    rollout = await _rollout(session)
    deadline = day.revealed_at + timedelta(days=FEEDBACK_DAYS)
    if day.revealed_at < rollout or SystemClock().now() > deadline:
        raise HTTPException(status.HTTP_409_CONFLICT, "Feedback window is closed")
    question = await session.scalar(
        select(Question)
        .join(QuizDayQuestion, QuizDayQuestion.question_id == Question.id)
        .where(
            QuizDayQuestion.quiz_day_id == day.id,
            QuizDayQuestion.question_id == question_id,
            Question.couple_id.is_(None),
        )
    )
    if question is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Quiz feedback is unavailable")
    return day, question, deadline


async def _rollout(session: AsyncSession) -> datetime:
    enabled = await session.scalar(
        select(QuizFeedbackRollout.enabled_at).where(
            QuizFeedbackRollout.feature == "question_feedback"
        )
    )
    if enabled is None:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "Feedback is being prepared")
    return enabled


async def _operation(
    session: AsyncSession, actor_id: UUID, operation_id: UUID
) -> QuestionFeedbackOperation | None:
    return await session.scalar(
        select(QuestionFeedbackOperation).where(
            QuestionFeedbackOperation.account_id == actor_id,
            QuestionFeedbackOperation.operation_id == operation_id,
        )
    )


def _record_operation(
    session: AsyncSession,
    actor_id: UUID,
    operation_id: UUID,
    feedback_id: UUID | None,
    action: str,
    result: QuizFeedbackView | QuizFeedbackDeleteResult,
) -> None:
    session.add(
        QuestionFeedbackOperation(
            account_id=actor_id,
            operation_id=operation_id,
            feedback_id=feedback_id,
            action=action,
            result_revision=result.revision,
            result_json=result.model_dump(mode="json"),
            created_at=SystemClock().now(),
        )
    )


def _feedback_view(record: QuestionFeedback) -> QuizFeedbackView:
    return QuizFeedbackView.model_validate(
        {
            "revision": record.revision,
            "stars": record.stars,
            "tags": record.tags,
            "review": record.sanitized_review,
            "review_status": record.review_status,
            "editable_until": record.editable_until,
            "updated_at": record.updated_at,
        }
    )
