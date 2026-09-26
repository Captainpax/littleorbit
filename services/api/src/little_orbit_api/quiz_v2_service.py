"""Transactional daily-quiz application service for RC5 clients."""

from datetime import date, timedelta
from typing import Literal
from uuid import UUID

from fastapi import HTTPException, status
from little_orbit_ai.pipeline import load_curated_bank
from little_orbit_ai.safety import normalized_hash
from sqlalchemy import delete, exists, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from .clock import SystemClock
from .couple_access import both_members_consent, lock_couple
from .models import (
    CoupleMember,
    Question,
    QuestionReport,
    QuizDay,
    QuizDayMember,
    QuizDayQuestion,
    QuizDraft,
    QuizOperation,
)
from .schemas import (
    QuizAnswerV2,
    QuizDayResponse,
    QuizHistoryItem,
    QuizOptionV2,
    QuizQuestionV2,
)

CATCH_UP_DAYS = 7
HISTORY_DAYS = 30
FALLBACK_ICONS = ("heart", "chat", "home", "meal", "movie", "music")


def utc_today() -> date:
    """Return the server-authoritative shared quiz date."""

    return SystemClock().now().date()


def require_visible_date(quiz_date: date) -> None:
    """Reject future dates and dates outside the public history window."""

    today = utc_today()
    if quiz_date > today or quiz_date < today - timedelta(days=HISTORY_DAYS - 1):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Quiz day is unavailable")


def date_is_editable(quiz_date: date) -> bool:
    """Return whether an incomplete date remains inside the catch-up window."""

    return quiz_date >= utc_today() - timedelta(days=CATCH_UP_DAYS)


async def materialize_day(
    session: AsyncSession, member: CoupleMember, quiz_date: date
) -> QuizDay:
    """Create one stable five-question snapshot under the couple lock."""

    require_visible_date(quiz_date)
    await lock_couple(session, member.couple_id)
    existing = await session.scalar(
        select(QuizDay).where(
            QuizDay.couple_id == member.couple_id, QuizDay.quiz_date == quiz_date
        ).with_for_update()
    )
    if existing is not None:
        return existing
    questions = await _questions_for_day(session, member.couple_id, quiz_date)
    if len(questions) != 5:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE, "Daily questions are being prepared"
        )
    day = QuizDay(
        couple_id=member.couple_id,
        quiz_date=quiz_date,
        revision=0,
        created_at=SystemClock().now(),
    )
    session.add(day)
    await session.flush()
    members = list(
        await session.scalars(
            select(CoupleMember).where(
                CoupleMember.couple_id == member.couple_id,
                CoupleMember.left_at.is_(None),
            )
        )
    )
    if len(members) != 2:
        raise HTTPException(status.HTTP_409_CONFLICT, "Couple membership is incomplete")
    session.add_all(
        [QuizDayMember(quiz_day_id=day.id, account_id=item.account_id) for item in members]
    )
    session.add_all(
        [
            QuizDayQuestion(quiz_day_id=day.id, question_id=item.id, position=index)
            for index, item in enumerate(questions, start=1)
        ]
    )
    await session.flush()
    return day


async def _questions_for_day(
    session: AsyncSession, couple_id: UUID, quiz_date: date
) -> list[Question]:
    intimacy = await both_members_consent(session, couple_id, "intimacy_enabled")
    custom = await _due_custom_questions(session, couple_id, quiz_date, intimacy)
    remaining = 5 - len(custom)
    global_items: list[Question] = []
    if remaining and intimacy:
        intimate = await session.scalar(
            select(Question)
            .where(
                Question.publish_date == quiz_date,
                Question.couple_id.is_(None),
                Question.intimacy.is_(True),
                Question.disabled_at.is_(None),
            )
            .order_by(Question.id)
        )
        if intimate is not None:
            global_items.append(intimate)
    general_needed = remaining - len(global_items)
    if general_needed:
        general = list(
            await session.scalars(
                select(Question)
                .where(
                    Question.publish_date == quiz_date,
                    Question.couple_id.is_(None),
                    Question.intimacy.is_(False),
                    Question.disabled_at.is_(None),
                )
                .order_by(Question.display_order.asc().nulls_last(), Question.id)
                .limit(general_needed)
            )
        )
        global_items = [*general, *global_items]
    return [*custom, *global_items]


async def _due_custom_questions(
    session: AsyncSession, couple_id: UUID, quiz_date: date, intimacy: bool
) -> list[Question]:
    linked = select(QuizDayQuestion.question_id)
    conditions = [
        Question.couple_id == couple_id,
        Question.publish_date <= quiz_date,
        Question.disabled_at.is_(None),
        Question.custom_slot.is_not(None),
        Question.id.not_in(linked),
    ]
    if not intimacy:
        conditions.append(Question.intimacy.is_(False))
    items = list(
        await session.scalars(
            select(Question)
            .where(*conditions)
            .order_by(Question.publish_date, Question.custom_slot, Question.id)
            .limit(5)
        )
    )
    return items


async def day_response(
    session: AsyncSession, day: QuizDay, actor_id: UUID
) -> QuizDayResponse:
    """Render one quiz day while withholding partner answers until shared reveal."""

    rows = list(
        (
            await session.execute(
                select(QuizDayQuestion, Question)
                .join(Question, Question.id == QuizDayQuestion.question_id)
                .where(QuizDayQuestion.quiz_day_id == day.id)
                .order_by(QuizDayQuestion.position)
            )
        ).all()
    )
    drafts = list(await session.scalars(select(QuizDraft).where(QuizDraft.quiz_day_id == day.id)))
    states = list(
        await session.scalars(select(QuizDayMember).where(QuizDayMember.quiz_day_id == day.id))
    )
    mine = {item.question_id: item for item in drafts if item.account_id == actor_id}
    partner = {item.question_id: item for item in drafts if item.account_id != actor_id}
    my_state = next(item for item in states if item.account_id == actor_id)
    partner_state = next(item for item in states if item.account_id != actor_id)
    revealed = day.revealed_at is not None
    questions = [
        _question_response(link, question, mine.get(question.id), partner.get(question.id), revealed)
        for link, question in rows
    ]
    status_value = _day_status(day, my_state, bool(mine))
    return QuizDayResponse(
        quiz_date=day.quiz_date,
        status=status_value,
        revision=day.revision,
        my_finished=my_state.completed_at is not None,
        partner_finished=partner_state.completed_at is not None,
        revealed=revealed,
        editable=date_is_editable(day.quiz_date) and not revealed,
        questions=questions,
    )


def _question_response(
    link: QuizDayQuestion,
    question: Question,
    mine: QuizDraft | None,
    partner: QuizDraft | None,
    revealed: bool,
) -> QuizQuestionV2:
    icons = question.option_icons or [
        FALLBACK_ICONS[i % len(FALLBACK_ICONS)] for i in range(len(question.options))
    ]
    options = [
        QuizOptionV2.model_validate(
            {"id": f"o{index}", "label": label, "icon_key": icons[index - 1]}
        )
        for index, label in enumerate(question.options, start=1)
    ]
    return QuizQuestionV2(
        id=question.id,
        position=link.position,
        interaction_version=question.interaction_version,
        kind=question.kind,
        prompt=question.prompt,
        category=question.category,
        intimacy=question.intimacy,
        options=options,
        scale_low_label=question.scale_low_label,
        scale_high_label=question.scale_high_label,
        my_answer=mine.answer if mine else None,
        my_answer_revision=mine.revision if mine else 0,
        partner_answer=partner.answer if revealed and partner else None,
    )


def _day_status(
    day: QuizDay, mine: QuizDayMember, has_drafts: bool
) -> Literal["not_started", "in_progress", "waiting", "revealed", "expired"]:
    if day.revealed_at is not None:
        return "revealed"
    if not date_is_editable(day.quiz_date):
        return "expired"
    if mine.completed_at is not None:
        return "waiting"
    return "in_progress" if has_drafts else "not_started"


def validate_answer(question: Question, answer: QuizAnswerV2) -> dict[str, object]:
    """Validate interaction kind and option coverage against persisted content."""

    payload = answer.model_dump(mode="json")
    kind = str(payload["kind"])
    if kind != question.kind:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Answer kind does not match")
    option_ids = {f"o{index}" for index in range(1, len(question.options) + 1)}
    supplied: set[str] = set()
    if kind == "single_choice":
        supplied = {str(payload["selected_option_id"])}
    elif kind == "multiple_choice":
        supplied = set(payload["selected_option_ids"])
    elif kind == "partner_guess":
        supplied = {str(payload["self_option_id"]), str(payload["guess_option_id"])}
    elif kind == "weighted_choice":
        supplied = set(payload["ratings"])
        if supplied != option_ids:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Every option needs a rating")
    if supplied and not supplied.issubset(option_ids):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Answer option is unavailable")
    return payload


async def operation_exists(
    session: AsyncSession, couple_id: UUID, actor_id: UUID, operation_id: UUID
) -> bool:
    """Return whether a retry-safe operation already completed."""

    return bool(
        await session.scalar(
            select(QuizOperation.id).where(
                QuizOperation.couple_id == couple_id,
                QuizOperation.account_id == actor_id,
                QuizOperation.operation_id == operation_id,
            )
        )
    )


def record_operation(
    session: AsyncSession,
    couple_id: UUID,
    actor_id: UUID,
    operation_id: UUID,
    action: str,
    quiz_date: date,
) -> None:
    """Record a content-free completed mutation for duplicate retries."""

    session.add(
        QuizOperation(
            couple_id=couple_id,
            account_id=actor_id,
            operation_id=operation_id,
            result={"action": action, "quiz_date": quiz_date.isoformat()},
            created_at=SystemClock().now(),
        )
    )


async def revoke_unrevealed_intimacy(session: AsyncSession, couple_id: UUID) -> None:
    """Replace unrevealed intimacy prompts immediately after either member opts out."""

    rows = (
        await session.execute(
            select(QuizDay, QuizDayQuestion)
            .join(QuizDayQuestion, QuizDayQuestion.quiz_day_id == QuizDay.id)
            .join(Question, Question.id == QuizDayQuestion.question_id)
            .where(
                QuizDay.couple_id == couple_id,
                QuizDay.revealed_at.is_(None),
                Question.intimacy.is_(True),
            )
        )
    ).all()
    for day, link in rows:
        prior_question_id = link.question_id
        replacement = await _general_replacement(session, day, couple_id)
        link.question_id = replacement.id
        await session.execute(
            delete(QuizDraft).where(
                QuizDraft.quiz_day_id == day.id,
                QuizDraft.question_id == prior_question_id,
            )
        )
        await session.execute(
            update(QuizDayMember)
            .where(QuizDayMember.quiz_day_id == day.id)
            .values(completed_at=None)
        )
        day.revision += 1


async def _general_replacement(
    session: AsyncSession, day: QuizDay, couple_id: UUID
) -> Question:
    """Find or create a safe non-intimacy replacement outside a day's snapshot."""

    used = select(QuizDayQuestion.question_id).where(QuizDayQuestion.quiz_day_id == day.id)
    candidate = await session.scalar(
        select(Question)
        .where(
            Question.publish_date == day.quiz_date,
            Question.couple_id.is_(None),
            Question.intimacy.is_(False),
            Question.disabled_at.is_(None),
            Question.id.not_in(used),
            ~exists(
                select(QuestionReport.id).where(
                    QuestionReport.question_id == Question.id,
                    QuestionReport.couple_id == couple_id,
                )
            ),
        )
        .order_by(Question.display_order.asc().nulls_last(), Question.id)
    )
    if candidate is not None:
        return candidate
    used_hashes = set(
        await session.scalars(
            select(Question.normalized_hash).where(Question.id.in_(used))
        )
    )
    item = next(
        question
        for question in load_curated_bank()
        if not question.intimacy and normalized_hash(question.prompt) not in used_hashes
    )
    fallback = Question(
        publish_date=day.quiz_date,
        kind=item.kind.value,
        prompt=item.prompt,
        category=item.category.value,
        intimacy=False,
        options=item.options,
        option_icons=[icon.value for icon in item.option_icons],
        scale_low_label=item.scale_low_label,
        scale_high_label=item.scale_high_label,
        interaction_version=2,
        source="consent_fallback",
        normalized_hash=normalized_hash(item.prompt),
        couple_id=couple_id,
        surprise=False,
    )
    session.add(fallback)
    await session.flush()
    return fallback


async def history_items(
    session: AsyncSession, member: CoupleMember
) -> list[QuizHistoryItem]:
    """Return thirty content-free day summaries without creating missing days."""

    first = utc_today() - timedelta(days=HISTORY_DAYS - 1)
    days = list(
        await session.scalars(
            select(QuizDay).where(
                QuizDay.couple_id == member.couple_id,
                QuizDay.quiz_date >= first,
                QuizDay.quiz_date <= utc_today(),
            )
        )
    )
    output: list[QuizHistoryItem] = []
    for day in sorted(days, key=lambda item: item.quiz_date, reverse=True):
        response = await day_response(session, day, member.account_id)
        answered = sum(item.my_answer is not None for item in response.questions)
        custom = await session.scalar(
            select(func.count())
            .select_from(QuizDayQuestion)
            .join(Question, Question.id == QuizDayQuestion.question_id)
            .where(
                QuizDayQuestion.quiz_day_id == day.id,
                Question.couple_id == member.couple_id,
                Question.source == "couple",
            )
        )
        output.append(
            QuizHistoryItem(
                quiz_date=day.quiz_date,
                status=response.status,
                answered_count=answered,
                custom_count=int(custom or 0),
            )
        )
    return output
