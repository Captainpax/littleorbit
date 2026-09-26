"""Little Orbit 1.3 quiz routes with themes and private feedback."""

from datetime import date
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from ..couple_access import active_member
from ..database import session_scope
from ..dependencies import current_account
from ..models import Account
from ..quiz_feedback_service import augment_day, augment_history
from ..quiz_v2_schemas import QuizDayMutation, QuizDraftMutation, QuizStatusResponse
from ..quiz_v2_service import day_response, history_items, materialize_day, utc_today
from ..quiz_v3_schemas import (
    QuizFeedbackDelete,
    QuizFeedbackDeleteResult,
    QuizFeedbackMutation,
    QuizFeedbackView,
)
from ..quiz_v4_schemas import QuizDayV4, QuizHistoryV4
from ..quiz_v4_service import augment_day_v4, augment_history_v4
from . import quizzes_v2, quizzes_v3

router = APIRouter(prefix="/v4/quizzes", tags=["quizzes-v4"])


@router.get("/today", response_model=QuizDayV4)
async def today_quiz(
    actor: Account = Depends(current_account),
    session: AsyncSession = Depends(session_scope),
) -> QuizDayV4:
    member = await active_member(session, actor.id)
    day = await materialize_day(session, member, utc_today())
    await session.commit()
    base = await augment_day(session, member, actor.id, await day_response(session, day, actor.id))
    return await augment_day_v4(session, base)


@router.get("/days/{quiz_date}", response_model=QuizDayV4)
async def quiz_day(
    quiz_date: date,
    actor: Account = Depends(current_account),
    session: AsyncSession = Depends(session_scope),
) -> QuizDayV4:
    member = await active_member(session, actor.id)
    day = await materialize_day(session, member, quiz_date)
    await session.commit()
    base = await augment_day(session, member, actor.id, await day_response(session, day, actor.id))
    return await augment_day_v4(session, base)


@router.get("/history", response_model=list[QuizHistoryV4])
async def quiz_history(
    days: int = 30,
    actor: Account = Depends(current_account),
    session: AsyncSession = Depends(session_scope),
) -> list[QuizHistoryV4]:
    if days != 30:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "History is fixed at 30 days")
    member = await active_member(session, actor.id)
    base = await augment_history(session, member, actor.id, await history_items(session, member))
    return await augment_history_v4(session, base)


@router.get("/status", response_model=QuizStatusResponse)
async def quiz_status(
    actor: Account = Depends(current_account),
    session: AsyncSession = Depends(session_scope),
) -> QuizStatusResponse:
    return await quizzes_v2.quiz_status(actor, session)


@router.put("/days/{quiz_date}/questions/{question_id}/draft", response_model=QuizDayV4)
async def put_draft(
    quiz_date: date,
    question_id: UUID,
    payload: QuizDraftMutation,
    actor: Account = Depends(current_account),
    session: AsyncSession = Depends(session_scope),
) -> QuizDayV4:
    await quizzes_v2.put_draft(quiz_date, question_id, payload, actor, session)
    return await quiz_day(quiz_date, actor, session)


@router.post("/days/{quiz_date}/finish", response_model=QuizDayV4)
async def finish(
    quiz_date: date,
    payload: QuizDayMutation,
    request: Request,
    actor: Account = Depends(current_account),
    session: AsyncSession = Depends(session_scope),
) -> QuizDayV4:
    await quizzes_v2.finish(quiz_date, payload, request, actor, session)
    return await quiz_day(quiz_date, actor, session)


@router.post("/days/{quiz_date}/reopen", response_model=QuizDayV4)
async def reopen(
    quiz_date: date,
    payload: QuizDayMutation,
    actor: Account = Depends(current_account),
    session: AsyncSession = Depends(session_scope),
) -> QuizDayV4:
    await quizzes_v2.reopen(quiz_date, payload, actor, session)
    return await quiz_day(quiz_date, actor, session)


@router.put(
    "/days/{quiz_date}/questions/{question_id}/feedback",
    response_model=QuizFeedbackView,
)
async def save_feedback(
    quiz_date: date,
    question_id: UUID,
    payload: QuizFeedbackMutation,
    actor: Account = Depends(current_account),
    session: AsyncSession = Depends(session_scope),
) -> QuizFeedbackView:
    return await quizzes_v3.save_feedback(quiz_date, question_id, payload, actor, session)


@router.delete(
    "/days/{quiz_date}/questions/{question_id}/feedback",
    response_model=QuizFeedbackDeleteResult,
)
async def remove_feedback(
    quiz_date: date,
    question_id: UUID,
    payload: QuizFeedbackDelete,
    actor: Account = Depends(current_account),
    session: AsyncSession = Depends(session_scope),
) -> QuizFeedbackDeleteResult:
    return await quizzes_v3.remove_feedback(quiz_date, question_id, payload, actor, session)
