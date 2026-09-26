"""Private custom-question queue and creator-owned pending mutations."""

from datetime import date, timedelta
from uuid import UUID

from fastapi import HTTPException, status
from little_orbit_ai.safety import normalized_hash
from sqlalchemy import exists, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from .couple_access import lock_couple
from .models import Question, QuizDayQuestion
from .quiz_v2_service import utc_today
from .schemas import CustomQuestionV2Request, CustomQuestionV2Response


async def create_custom(
    session: AsyncSession,
    couple_id: UUID,
    actor_id: UUID,
    payload: CustomQuestionV2Request,
) -> Question:
    """Assign a custom prompt to the earliest future UTC day with a free slot."""

    await lock_couple(session, couple_id)
    digest = normalized_hash(payload.prompt)
    duplicate = await session.scalar(
        select(Question.id).where(
            Question.couple_id == couple_id,
            Question.normalized_hash == digest,
            Question.disabled_at.is_(None),
            Question.publish_date >= utc_today(),
        )
    )
    if duplicate is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, "That question is already queued")
    publish_date, slot = await _next_slot(session, couple_id, utc_today() + timedelta(days=1))
    question = _new_question(payload, couple_id, actor_id, publish_date, slot)
    session.add(question)
    await session.flush()
    return question


async def update_custom(
    session: AsyncSession,
    couple_id: UUID,
    actor_id: UUID,
    question_id: UUID,
    payload: CustomQuestionV2Request,
) -> Question:
    """Edit a creator-owned prompt before its UTC publication date."""

    await lock_couple(session, couple_id)
    question = await _owned_pending(session, couple_id, actor_id, question_id)
    question.kind = payload.kind
    question.prompt = payload.prompt
    question.category = payload.category
    question.intimacy = payload.intimacy
    question.options = [item.label for item in payload.options]
    question.option_icons = [item.icon_key for item in payload.options]
    question.scale_low_label = payload.scale_low_label
    question.scale_high_label = payload.scale_high_label
    question.normalized_hash = normalized_hash(payload.prompt)
    question.surprise = payload.surprise
    await session.flush()
    return question


async def delete_custom(
    session: AsyncSession, couple_id: UUID, actor_id: UUID, question_id: UUID
) -> None:
    """Delete a creator-owned prompt that has not entered a daily snapshot."""

    await lock_couple(session, couple_id)
    question = await _owned_pending(session, couple_id, actor_id, question_id)
    await session.delete(question)


async def creator_queue(
    session: AsyncSession, couple_id: UUID, actor_id: UUID
) -> tuple[list[CustomQuestionV2Response], list[CustomQuestionV2Response], int]:
    """Return the caller's content and only a count for partner surprises."""

    pending_filter = ~exists(
        select(QuizDayQuestion.id).where(QuizDayQuestion.question_id == Question.id)
    )
    mine = list(
        await session.scalars(
            select(Question).where(
                Question.couple_id == couple_id,
                Question.created_by == actor_id,
                Question.custom_slot.is_not(None),
                pending_filter,
            ).order_by(Question.publish_date, Question.custom_slot)
        )
    )
    shared = list(
        await session.scalars(
            select(Question).where(
                Question.couple_id == couple_id,
                Question.created_by != actor_id,
                Question.surprise.is_(False),
                Question.custom_slot.is_not(None),
                pending_filter,
            ).order_by(Question.publish_date, Question.custom_slot)
        )
    )
    partner_count = await session.scalar(
        select(func.count()).select_from(Question).where(
            Question.couple_id == couple_id,
            Question.created_by != actor_id,
            Question.surprise.is_(True),
            Question.custom_slot.is_not(None),
            pending_filter,
        )
    )
    return (
        [_custom_response(item) for item in mine],
        [_custom_response(item) for item in shared],
        int(partner_count or 0),
    )


async def _next_slot(
    session: AsyncSession, couple_id: UUID, start: date
) -> tuple[date, int]:
    target = start
    for _ in range(366):
        slots = set(
            await session.scalars(
                select(Question.custom_slot).where(
                    Question.couple_id == couple_id,
                    Question.publish_date == target,
                    Question.custom_slot.is_not(None),
                )
            )
        )
        for slot in range(1, 6):
            if slot not in slots:
                return target, slot
        target += timedelta(days=1)
    raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "Custom queue is full")


def _new_question(
    payload: CustomQuestionV2Request,
    couple_id: UUID,
    actor_id: UUID,
    publish_date: date,
    slot: int,
) -> Question:
    return Question(
        publish_date=publish_date,
        kind=payload.kind,
        prompt=payload.prompt,
        category=payload.category,
        intimacy=payload.intimacy,
        options=[item.label for item in payload.options],
        option_icons=[item.icon_key for item in payload.options],
        scale_low_label=payload.scale_low_label,
        scale_high_label=payload.scale_high_label,
        interaction_version=2,
        source="couple",
        normalized_hash=normalized_hash(payload.prompt),
        couple_id=couple_id,
        created_by=actor_id,
        custom_slot=slot,
        surprise=payload.surprise,
    )


async def _owned_pending(
    session: AsyncSession, couple_id: UUID, actor_id: UUID, question_id: UUID
) -> Question:
    linked = exists(
        select(QuizDayQuestion.id).where(QuizDayQuestion.question_id == question_id)
    )
    question = await session.scalar(
        select(Question)
        .where(
            Question.id == question_id,
            Question.couple_id == couple_id,
            Question.created_by == actor_id,
            Question.custom_slot.is_not(None),
            Question.publish_date > utc_today(),
            ~linked,
        )
        .with_for_update()
    )
    if question is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Custom question is unavailable")
    return question


def _custom_response(question: Question) -> CustomQuestionV2Response:
    return CustomQuestionV2Response(
        id=question.id,
        publish_date=question.publish_date,
        custom_slot=question.custom_slot or 1,
        prompt=question.prompt,
        kind=question.kind,
        category=question.category,
        surprise=question.surprise,
    )
