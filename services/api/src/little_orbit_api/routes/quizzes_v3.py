"""Little Orbit 1.2 quiz routes with private per-question feedback."""

from datetime import date
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from ..couple_access import active_member
from ..database import session_scope
from ..dependencies import current_account
from ..models import Account
from ..quiz_feedback_service import (
    augment_day,
    augment_history,
    delete_feedback,
    put_feedback,
)
from ..quiz_v2_schemas import QuizDayMutation, QuizDraftMutation, QuizStatusResponse
from ..quiz_v2_service import day_response, history_items, materialize_day, utc_today
from ..quiz_v3_schemas import (
    QuizDayV3,
    QuizFeedbackDelete,
    QuizFeedbackDeleteResult,
    QuizFeedbackMutation,
    QuizFeedbackView,
    QuizHistoryV3,
)
from . import quizzes_v2

router = APIRouter(prefix="/v3/quizzes", tags=["quizzes-v3"])


@router.get("/today", response_model=QuizDayV3)
async def today_quiz(
    actor: Account = Depends(current_account),
    session: AsyncSession = Depends(session_scope),
) -> QuizDayV3:
    member = await active_member(session, actor.id)
    day = await materialize_day(session, member, utc_today())
    await session.commit()
    return await augment_day(session, member, actor.id, await day_response(session, day, actor.id))


@router.get("/days/{quiz_date}", response_model=QuizDayV3)
async def quiz_day(
    quiz_date: date,
    actor: Account = Depends(current_account),
    session: AsyncSession = Depends(session_scope),
) -> QuizDayV3:
    member = await active_member(session, actor.id)
    day = await materialize_day(session, member, quiz_date)
    await session.commit()
    return await augment_day(session, member, actor.id, await day_response(session, day, actor.id))


@router.get("/history", response_model=list[QuizHistoryV3])
async def quiz_history(
    days: int = 30,
    actor: Account = Depends(current_account),
    session: AsyncSession = Depends(session_scope),
) -> list[QuizHistoryV3]:
    if days != 30:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "History is fixed at 30 days")
    member = await active_member(session, actor.id)
    return await augment_history(session, member, actor.id, await history_items(session, member))


@router.get("/status", response_model=QuizStatusResponse)
async def quiz_status(
    actor: Account = Depends(current_account),
    session: AsyncSession = Depends(session_scope),
) -> QuizStatusResponse:
    return await quizzes_v2.quiz_status(actor, session)


@router.put("/days/{quiz_date}/questions/{question_id}/draft", response_model=QuizDayV3)
async def put_draft(
    quiz_date: date,
    question_id: UUID,
    payload: QuizDraftMutation,
    actor: Account = Depends(current_account),
    session: AsyncSession = Depends(session_scope),
) -> QuizDayV3:
    base = await quizzes_v2.put_draft(quiz_date, question_id, payload, actor, session)
    member = await active_member(session, actor.id)
    return await augment_day(session, member, actor.id, base)


@router.post("/days/{quiz_date}/finish", response_model=QuizDayV3)
async def finish(
    quiz_date: date,
    payload: QuizDayMutation,
    request: Request,
    actor: Account = Depends(current_account),
    session: AsyncSession = Depends(session_scope),
) -> QuizDayV3:
    base = await quizzes_v2.finish(quiz_date, payload, request, actor, session)
    member = await active_member(session, actor.id)
    return await augment_day(session, member, actor.id, base)


@router.post("/days/{quiz_date}/reopen", response_model=QuizDayV3)
async def reopen(
    quiz_date: date,
    payload: QuizDayMutation,
    actor: Account = Depends(current_account),
    session: AsyncSession = Depends(session_scope),
) -> QuizDayV3:
    base = await quizzes_v2.reopen(quiz_date, payload, actor, session)
    member = await active_member(session, actor.id)
    return await augment_day(session, member, actor.id, base)


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
    member = await active_member(session, actor.id)
    response = await put_feedback(session, member, actor.id, quiz_date, question_id, payload)
    await session.commit()
    return response


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
    member = await active_member(session, actor.id)
    response = await delete_feedback(session, member, actor.id, quiz_date, question_id, payload)
    await session.commit()
    return response
