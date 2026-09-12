"""RC5 daily quiz, history, custom queue, and private draft routes."""

from datetime import date
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Response, status
from little_orbit_ai.pipeline import load_curated_bank
from little_orbit_ai.safety import normalized_hash
from sqlalchemy import delete, exists, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from ..clock import SystemClock
from ..couple_access import active_member, both_members_consent, lock_couple
from ..database import session_scope
from ..dependencies import current_account
from ..models import (
    Account,
    Question,
    QuestionReport,
    QuizDay,
    QuizDayMember,
    QuizDayQuestion,
    QuizDraft,
)
from ..quiz_custom_service import create_custom, creator_queue, delete_custom, update_custom
from ..quiz_v2_mutations import finish_day, reopen_day, save_draft
from ..quiz_v2_service import day_response, history_items, materialize_day, utc_today
from ..schemas import (
    CustomQuestionV2Request,
    CustomQuestionV2Response,
    CustomQueueResponse,
    PublicMessage,
    QuestionReportV2Request,
    QuizDayMutation,
    QuizDayResponse,
    QuizDraftMutation,
    QuizHistoryItem,
    QuizStatusResponse,
)

router = APIRouter(prefix="/v2/quizzes", tags=["quizzes-v2"])


@router.get("/today", response_model=QuizDayResponse)
async def today_quiz(
    actor: Account = Depends(current_account),
    session: AsyncSession = Depends(session_scope),
) -> QuizDayResponse:
    """Return the server-authoritative UTC quiz for the active couple."""

    member = await active_member(session, actor.id)
    day = await materialize_day(session, member, utc_today())
    await session.commit()
    return await day_response(session, day, actor.id)


@router.get("/days/{quiz_date}", response_model=QuizDayResponse)
async def quiz_day(
    quiz_date: date,
    actor: Account = Depends(current_account),
    session: AsyncSession = Depends(session_scope),
) -> QuizDayResponse:
    """Return one visible current or historical UTC quiz day."""

    member = await active_member(session, actor.id)
    day = await materialize_day(session, member, quiz_date)
    await session.commit()
    return await day_response(session, day, actor.id)


@router.get("/history", response_model=list[QuizHistoryItem])
async def quiz_history(
    days: int = 30,
    actor: Account = Depends(current_account),
    session: AsyncSession = Depends(session_scope),
) -> list[QuizHistoryItem]:
    """Return the fixed thirty-day privacy-safe navigation window."""

    if days != 30:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "History window must be 30 days")
    member = await active_member(session, actor.id)
    return await history_items(session, member)


@router.get("/status", response_model=QuizStatusResponse)
async def quiz_status(
    actor: Account = Depends(current_account),
    session: AsyncSession = Depends(session_scope),
) -> QuizStatusResponse:
    """Return content-free state suitable for delayed Android polling."""

    member = await active_member(session, actor.id)
    day = await materialize_day(session, member, utc_today())
    await session.commit()
    rendered = await day_response(session, day, actor.id)
    return QuizStatusResponse(
        quiz_date=rendered.quiz_date,
        state_version=rendered.revision,
        my_finished=rendered.my_finished,
        partner_finished=rendered.partner_finished,
        revealed=rendered.revealed,
    )


@router.put(
    "/days/{quiz_date}/questions/{question_id}/draft", response_model=QuizDayResponse
)
async def put_draft(
    quiz_date: date,
    question_id: UUID,
    payload: QuizDraftMutation,
    actor: Account = Depends(current_account),
    session: AsyncSession = Depends(session_scope),
) -> QuizDayResponse:
    """Save one private optimistic draft without exposing partner progress."""

    member = await active_member(session, actor.id)
    day = await materialize_day(session, member, quiz_date)
    await save_draft(session, day, actor.id, question_id, payload)
    await session.commit()
    return await day_response(session, day, actor.id)


@router.post("/days/{quiz_date}/finish", response_model=QuizDayResponse)
async def finish(
    quiz_date: date,
    payload: QuizDayMutation,
    actor: Account = Depends(current_account),
    session: AsyncSession = Depends(session_scope),
) -> QuizDayResponse:
    """Finish after review and reveal only if both active members finished."""

    member = await active_member(session, actor.id)
    day = await materialize_day(session, member, quiz_date)
    await finish_day(session, day, actor.id, payload)
    await session.commit()
    return await day_response(session, day, actor.id)


@router.post("/days/{quiz_date}/reopen", response_model=QuizDayResponse)
async def reopen(
    quiz_date: date,
    payload: QuizDayMutation,
    actor: Account = Depends(current_account),
    session: AsyncSession = Depends(session_scope),
) -> QuizDayResponse:
    """Reopen the caller's drafts before the partner completes the reveal."""

    member = await active_member(session, actor.id)
    day = await materialize_day(session, member, quiz_date)
    await reopen_day(session, day, actor.id, payload)
    await session.commit()
    return await day_response(session, day, actor.id)


@router.get("/custom", response_model=CustomQueueResponse)
async def custom_queue(
    actor: Account = Depends(current_account),
    session: AsyncSession = Depends(session_scope),
) -> CustomQueueResponse:
    """Return creator content and a count-only view of partner surprises."""

    member = await active_member(session, actor.id)
    mine, shared, partner_count = await creator_queue(session, member.couple_id, actor.id)
    return CustomQueueResponse(
        mine=mine, shared=shared, partner_surprise_count=partner_count
    )


@router.post("/custom", response_model=CustomQuestionV2Response, status_code=201)
async def post_custom(
    payload: CustomQuestionV2Request,
    actor: Account = Depends(current_account),
    session: AsyncSession = Depends(session_scope),
) -> CustomQuestionV2Response:
    """Queue one creator-owned custom question."""

    member = await active_member(session, actor.id)
    question = await create_custom(session, member.couple_id, actor.id, payload)
    await session.commit()
    return _custom_response(question)


@router.put("/custom/{question_id}", response_model=CustomQuestionV2Response)
async def put_custom(
    question_id: UUID,
    payload: CustomQuestionV2Request,
    actor: Account = Depends(current_account),
    session: AsyncSession = Depends(session_scope),
) -> CustomQuestionV2Response:
    """Edit one creator-owned unpublished custom question."""

    member = await active_member(session, actor.id)
    question = await update_custom(session, member.couple_id, actor.id, question_id, payload)
    await session.commit()
    return _custom_response(question)


@router.delete("/custom/{question_id}", status_code=204)
async def remove_custom(
    question_id: UUID,
    actor: Account = Depends(current_account),
    session: AsyncSession = Depends(session_scope),
) -> Response:
    """Delete one creator-owned unpublished custom question."""

    member = await active_member(session, actor.id)
    await delete_custom(session, member.couple_id, actor.id, question_id)
    await session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/questions/{question_id}/report", response_model=PublicMessage)
async def report_question(
    question_id: UUID,
    payload: QuestionReportV2Request,
    actor: Account = Depends(current_account),
    session: AsyncSession = Depends(session_scope),
) -> PublicMessage:
    """Hide an unrevealed question, clear its drafts, and insert a safe replacement."""

    member = await active_member(session, actor.id)
    await lock_couple(session, member.couple_id)
    day, link, question = await _report_target(session, member.couple_id, question_id)
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
                reason=payload.reason_code,
                created_at=SystemClock().now(),
            )
        )
        if day.revealed_at is None:
            await _replace_reported(session, day, link, question, member.couple_id)
        await session.commit()
    return PublicMessage(message="Question hidden for your couple and sent for review.")


async def _report_target(
    session: AsyncSession, couple_id: UUID, question_id: UUID
) -> tuple[QuizDay, QuizDayQuestion, Question]:
    row = (
        await session.execute(
            select(QuizDay, QuizDayQuestion, Question)
            .join(QuizDayQuestion, QuizDayQuestion.quiz_day_id == QuizDay.id)
            .join(Question, Question.id == QuizDayQuestion.question_id)
            .where(QuizDay.couple_id == couple_id, Question.id == question_id)
            .order_by(QuizDay.quiz_date.desc())
            .limit(1)
            .with_for_update()
        )
    ).first()
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Question is unavailable")
    return row[0], row[1], row[2]


async def _replace_reported(
    session: AsyncSession,
    day: QuizDay,
    link: QuizDayQuestion,
    reported: Question,
    couple_id: UUID,
) -> None:
    used = select(QuizDayQuestion.question_id).where(QuizDayQuestion.quiz_day_id == day.id)
    consent = await both_members_consent(session, couple_id, "intimacy_enabled")
    replacement = await session.scalar(
        select(Question)
        .where(
            Question.publish_date == day.quiz_date,
            Question.couple_id.is_(None),
            Question.disabled_at.is_(None),
            Question.id.not_in(used),
            Question.intimacy.is_(consent if reported.intimacy else False),
            ~exists(
                select(QuestionReport.id).where(
                    QuestionReport.question_id == Question.id,
                    QuestionReport.couple_id == couple_id,
                )
            ),
        )
        .order_by(Question.display_order.asc().nulls_last(), Question.id)
    )
    if replacement is None:
        replacement = await _curated_replacement(
            session, day.quiz_date, couple_id, reported.intimacy and consent
        )
    link.question_id = replacement.id
    await session.execute(
        delete(QuizDraft).where(
            QuizDraft.quiz_day_id == day.id, QuizDraft.question_id == reported.id
        )
    )
    await session.execute(
        update(QuizDayMember)
        .where(QuizDayMember.quiz_day_id == day.id)
        .values(completed_at=None)
    )
    day.revision += 1


async def _curated_replacement(
    session: AsyncSession, quiz_date: date, couple_id: UUID, allow_intimacy: bool
) -> Question:
    for item in load_curated_bank():
        if item.intimacy != allow_intimacy:
            continue
        digest = normalized_hash(item.prompt)
        present = await session.scalar(
            select(Question.id).where(
                Question.publish_date == quiz_date,
                Question.couple_id == couple_id,
                Question.normalized_hash == digest,
            )
        )
        if present is None:
            question = Question(
                publish_date=quiz_date,
                kind=item.kind.value,
                prompt=item.prompt,
                category=item.category.value,
                intimacy=item.intimacy,
                options=item.options,
                option_icons=[icon.value for icon in item.option_icons],
                scale_low_label=item.scale_low_label,
                scale_high_label=item.scale_high_label,
                interaction_version=2,
                source="report_fallback",
                normalized_hash=digest,
                couple_id=couple_id,
                surprise=False,
            )
            session.add(question)
            await session.flush()
            return question
    raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "No safe replacement is available")


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
