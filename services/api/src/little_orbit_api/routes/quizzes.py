"""Daily question delivery and private-until-both-submit answers."""

from datetime import date
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, status
from little_orbit_ai.pipeline import load_curated_bank
from little_orbit_ai.safety import normalized_hash
from sqlalchemy import exists, or_, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql.elements import ColumnElement

from ..clock import SystemClock
from ..couple_access import active_member, both_members_consent, lock_couple
from ..database import session_scope
from ..dependencies import current_account
from ..models import Account, CoupleMember, Question, QuestionReport, QuizAnswer
from ..schemas import (
    CustomQuestionRequest,
    PublicMessage,
    QuestionReportRequest,
    QuestionResponse,
    QuizAnswerRequest,
)

router = APIRouter(prefix="/v1/quizzes", tags=["quizzes"])


async def _intimacy_enabled(session: AsyncSession, couple_id: UUID) -> bool:
    return await both_members_consent(session, couple_id, "intimacy_enabled")


def _visible_question(couple_id: UUID) -> ColumnElement[bool]:
    return or_(Question.couple_id.is_(None), Question.couple_id == couple_id)


def _not_reported(couple_id: UUID) -> ColumnElement[bool]:
    return ~exists(
        select(QuestionReport.id).where(
            QuestionReport.question_id == Question.id,
            QuestionReport.couple_id == couple_id,
            QuestionReport.resolved_at.is_(None),
        )
    )


def _validate_answer(question: Question, answer: dict[str, object]) -> None:
    values = answer.get("values")
    text = answer.get("text")
    rating = answer.get("rating")
    if question.kind == "free_text" and (not isinstance(text, str) or not 1 <= len(text) <= 2_000):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Free-text answer is invalid")
    if question.kind == "weighted_scale" and (not isinstance(rating, int) or not 1 <= rating <= 5):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Rating must be between 1 and 5")
    if question.kind in {"single_choice", "partner_guess"} and (
        not isinstance(values, list) or len(values) != 1 or values[0] not in question.options
    ):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Choice answer is invalid")
    if question.kind == "multiple_choice" and (
        not isinstance(values, list) or not values or not set(values).issubset(question.options)
    ):
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY, "Multiple-choice answer is invalid"
        )


async def _responses(
    session: AsyncSession, questions: list[Question], member: CoupleMember
) -> list[QuestionResponse]:
    ids = [question.id for question in questions]
    answers = list(
        await session.scalars(
            select(QuizAnswer).where(
                QuizAnswer.couple_id == member.couple_id, QuizAnswer.question_id.in_(ids)
            )
        )
    )
    by_question: dict[UUID, list[QuizAnswer]] = {}
    for answer in answers:
        by_question.setdefault(answer.question_id, []).append(answer)
    output: list[QuestionResponse] = []
    for question in questions:
        current = by_question.get(question.id, [])
        mine = next((item for item in current if item.account_id == member.account_id), None)
        partner = next((item for item in current if item.account_id != member.account_id), None)
        revealed = mine is not None and partner is not None
        output.append(
            QuestionResponse(
                id=question.id,
                publish_date=question.publish_date,
                kind=question.kind,
                prompt=question.prompt,
                category=question.category,
                options=question.options,
                submitted_by_me=mine is not None,
                both_submitted=revealed,
                my_answer=mine.answer if revealed and mine is not None else None,
                partner_answer=partner.answer if revealed and partner is not None else None,
            )
        )
    return output


@router.get("/daily", response_model=list[QuestionResponse])
async def daily_questions(
    local_date: date,
    actor: Account = Depends(current_account),
    session: AsyncSession = Depends(session_scope),
) -> list[QuestionResponse]:
    """Return exactly five date-based questions allowed by both partners' current settings."""

    member = await active_member(session, actor.id)
    general = list(
        await session.scalars(
            select(Question)
            .where(
                Question.publish_date == local_date,
                Question.intimacy.is_(False),
                Question.disabled_at.is_(None),
                _visible_question(member.couple_id),
                _not_reported(member.couple_id),
            )
            .order_by(Question.couple_id.is_(None), Question.id)
            .limit(5)
        )
    )
    if len(general) < 5:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE, "Daily questions are being prepared"
        )
    if await _intimacy_enabled(session, member.couple_id):
        intimacy = await session.scalar(
            select(Question)
            .where(
                Question.publish_date == local_date,
                Question.intimacy.is_(True),
                Question.disabled_at.is_(None),
                _visible_question(member.couple_id),
                _not_reported(member.couple_id),
            )
            .order_by(Question.couple_id.is_(None), Question.id)
        )
        if intimacy is not None:
            general[-1] = intimacy
    return await _responses(session, general, member)


@router.put("/daily/{question_id}/answer", response_model=list[QuestionResponse])
async def submit_answer(
    question_id: UUID,
    payload: QuizAnswerRequest,
    actor: Account = Depends(current_account),
    session: AsyncSession = Depends(session_scope),
) -> list[QuestionResponse]:
    """Store one answer idempotently and reveal only after both active members submit."""

    member = await active_member(session, actor.id)
    await lock_couple(session, member.couple_id)
    question = await session.scalar(
        select(Question).where(Question.id == question_id, Question.disabled_at.is_(None))
    )
    unavailable = (
        question is None
        or (question.couple_id is not None and question.couple_id != member.couple_id)
        or await session.scalar(
            select(
                exists().where(
                    QuestionReport.question_id == question_id,
                    QuestionReport.couple_id == member.couple_id,
                    QuestionReport.resolved_at.is_(None),
                )
            )
        )
    )
    if unavailable or question is None or (
        question.intimacy and not await _intimacy_enabled(session, member.couple_id)
    ):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Question is unavailable")
    _validate_answer(question, payload.answer)
    now = SystemClock().now()
    await session.execute(
        insert(QuizAnswer)
        .values(
            id=uuid4(),
            question_id=question_id,
            couple_id=member.couple_id,
            account_id=actor.id,
            answer=payload.answer,
            submitted_at=now,
        )
        .on_conflict_do_update(
            index_elements=["question_id", "account_id"],
            set_={"answer": payload.answer, "submitted_at": now},
        )
    )
    await session.commit()
    return await _responses(session, [question], member)


@router.post("/custom", response_model=QuestionResponse, status_code=status.HTTP_201_CREATED)
async def create_custom_question(
    payload: CustomQuestionRequest,
    actor: Account = Depends(current_account),
    session: AsyncSession = Depends(session_scope),
) -> QuestionResponse:
    """Create a couple-scoped prompt that either active partner may answer."""

    member = await active_member(session, actor.id)
    await lock_couple(session, member.couple_id)
    question = Question(
        publish_date=payload.publish_date,
        kind=payload.kind,
        prompt=payload.prompt,
        category=payload.category,
        intimacy=payload.intimacy,
        options=payload.options,
        source="couple",
        normalized_hash=normalized_hash(payload.prompt),
        couple_id=member.couple_id,
        created_by=actor.id,
    )
    session.add(question)
    await session.commit()
    await session.refresh(question)
    return (await _responses(session, [question], member))[0]


async def _add_report_replacement(
    session: AsyncSession, member: CoupleMember, reported: Question
) -> None:
    existing_hashes = set(
        await session.scalars(
            select(Question.normalized_hash).where(
                Question.publish_date == reported.publish_date,
                Question.couple_id == member.couple_id,
            )
        )
    )
    for candidate in load_curated_bank():
        digest = normalized_hash(candidate.prompt)
        if candidate.intimacy or digest in existing_hashes or candidate.prompt == reported.prompt:
            continue
        session.add(
            Question(
                publish_date=reported.publish_date,
                kind=candidate.kind.value,
                prompt=candidate.prompt,
                category=candidate.category.value,
                intimacy=False,
                options=candidate.options,
                source="report_fallback",
                normalized_hash=digest,
                couple_id=member.couple_id,
                created_by=None,
            )
        )
        return
    raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "No safe replacement is available")


@router.post("/{question_id}/report", response_model=PublicMessage)
async def report_question(
    question_id: UUID,
    payload: QuestionReportRequest,
    actor: Account = Depends(current_account),
    session: AsyncSession = Depends(session_scope),
) -> PublicMessage:
    """Hide a question for this couple immediately and queue metadata for owner review."""

    member = await active_member(session, actor.id)
    await lock_couple(session, member.couple_id)
    question = await session.get(Question, question_id)
    if question is None or (
        question.couple_id is not None and question.couple_id != member.couple_id
    ):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Question is unavailable")
    prior = await session.scalar(
        select(QuestionReport).where(
            QuestionReport.question_id == question_id,
            QuestionReport.couple_id == member.couple_id,
        )
    )
    if prior is None:
        session.add(
            QuestionReport(
                question_id=question_id,
                couple_id=member.couple_id,
                reporter_id=actor.id,
                reason=payload.reason,
                created_at=SystemClock().now(),
            )
        )
        await _add_report_replacement(session, member, question)
        await session.commit()
    return PublicMessage(message="Question hidden for your couple and sent for review.")
