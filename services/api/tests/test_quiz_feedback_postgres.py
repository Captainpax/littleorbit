"""Optional PostgreSQL coverage for private feedback replay and retention."""

import os
from datetime import UTC, date, datetime, timedelta
from uuid import uuid4

import pytest
import pytest_asyncio
from fastapi import HTTPException
from sqlalchemy import func, inspect, select, text

pytestmark = [
    pytest.mark.skipif(
        not os.getenv("LITTLE_ORBIT_TEST_DATABASE_URL"),
        reason="set LITTLE_ORBIT_TEST_DATABASE_URL to an isolated PostgreSQL database",
    ),
    pytest.mark.asyncio(loop_scope="session"),
]

from little_orbit_api.database import Base, SessionFactory, engine  # noqa: E402
from little_orbit_api.models import (  # noqa: E402
    Account,
    Couple,
    CoupleMember,
    Question,
    QuizDay,
    QuizDayQuestion,
)
from little_orbit_api.quiz_feedback_retention import (  # noqa: E402
    enforce_feedback_retention,
)
from little_orbit_api.quiz_feedback_service import (  # noqa: E402
    delete_feedback,
    put_feedback,
)
from little_orbit_api.quiz_intelligence_models import (  # noqa: E402
    AnonymousQuestionReview,
    QuestionFeedback,
    QuestionFeedbackOperation,
    QuizFeedbackRollout,
)
from little_orbit_api.quiz_v3_schemas import (  # noqa: E402
    QuizFeedbackDelete,
    QuizFeedbackMutation,
)


@pytest_asyncio.fixture(autouse=True, loop_scope="session")
async def clean_database() -> None:
    async with engine.begin() as connection:
        existing = set(await connection.run_sync(lambda sync: inspect(sync).get_table_names()))
        quote = connection.dialect.identifier_preparer.quote
        tables = ", ".join(
            quote(table.name) for table in Base.metadata.sorted_tables if table.name in existing
        )
        await connection.execute(text(f"TRUNCATE TABLE {tables} RESTART IDENTITY CASCADE"))


async def _feedback_fixture() -> tuple[CoupleMember, Account, Question, QuizDay]:
    now = datetime.now(UTC)
    actor = _account("one@example.com", "One", now)
    partner = _account("two@example.com", "Two", now)
    couple = Couple(created_at=now, updated_at=now)
    member = CoupleMember(couple_id=couple.id, account_id=actor.id, joined_at=now)
    other_member = CoupleMember(couple_id=couple.id, account_id=partner.id, joined_at=now)
    question = _question()
    day = QuizDay(
        couple_id=couple.id,
        quiz_date=date.today(),
        revision=2,
        revealed_at=now,
        created_at=now,
    )
    async with SessionFactory() as session:
        session.add_all([actor, partner, couple])
        await session.flush()
        member.couple_id = couple.id
        member.account_id = actor.id
        other_member.couple_id = couple.id
        other_member.account_id = partner.id
        question.id = uuid4()
        day.couple_id = couple.id
        session.add_all([member, other_member, question, day])
        await session.flush()
        session.add(QuizDayQuestion(quiz_day_id=day.id, question_id=question.id, position=1))
        session.add(
            QuizFeedbackRollout(
                feature="question_feedback", enabled_at=now - timedelta(minutes=1)
            )
        )
        await session.commit()
    return member, actor, question, day


def _account(email: str, name: str, now: datetime) -> Account:
    return Account(
        email_normalized=email,
        password_hash="not-used",
        display_name=name,
        is_adult=True,
        accepted_terms_version="2026-09-10",
        verified_at=now,
        created_at=now,
        updated_at=now,
    )


def _question() -> Question:
    return Question(
        publish_date=date.today(),
        kind="free_text",
        prompt="What small moment made today feel warmer for you?",
        category="connection",
        intimacy=False,
        options=[],
        option_icons=[],
        interaction_version=2,
        display_order=1,
        source="test",
        normalized_hash="a" * 64,
    )


async def test_feedback_insert_replay_edit_delete_and_retention() -> None:
    member, actor, question, day = await _feedback_fixture()
    create_id = uuid4()
    create = QuizFeedbackMutation(
        operation_id=create_id,
        expected_revision=0,
        stars=4,
        tags=["meaningful", "clear"],
        review="It gave us something new to discuss.",
        review_consent=True,
    )
    async with SessionFactory() as session:
        saved = await put_feedback(
            session, member, actor.id, day.quiz_date, question.id, create
        )
        await session.commit()
        assert saved.revision == 1
        replay = await put_feedback(
            session, member, actor.id, day.quiz_date, question.id, create
        )
        assert replay == saved
        assert await session.scalar(select(func.count()).select_from(QuestionFeedback)) == 1

        edited = await put_feedback(
            session,
            member,
            actor.id,
            day.quiz_date,
            question.id,
            QuizFeedbackMutation(
                operation_id=uuid4(),
                expected_revision=1,
                stars=5,
                tags=["sparked_conversation"],
            ),
        )
        await session.commit()
        assert edited.revision == 2
        deleted = await delete_feedback(
            session,
            member,
            actor.id,
            day.quiz_date,
            question.id,
            QuizFeedbackDelete(operation_id=uuid4(), expected_revision=2),
        )
        await session.commit()
        assert deleted.deleted
        assert await session.scalar(select(func.count()).select_from(QuestionFeedback)) == 0


async def test_closed_window_unlinks_identity_and_hard_deletes_review() -> None:
    member, actor, question, day = await _feedback_fixture()
    revealed_at = day.revealed_at
    assert revealed_at is not None
    async with SessionFactory() as session:
        await put_feedback(
            session,
            member,
            actor.id,
            day.quiz_date,
            question.id,
            QuizFeedbackMutation(
                operation_id=uuid4(),
                expected_revision=0,
                stars=5,
                tags=["fun"],
                review="A delightful change of pace.",
                review_consent=True,
            ),
        )
        await session.commit()
        await enforce_feedback_retention(session, revealed_at + timedelta(days=31))
        await session.commit()
        assert await session.scalar(select(func.count()).select_from(QuestionFeedback)) == 0
        anonymous = await session.scalar(select(AnonymousQuestionReview))
        assert anonymous is not None
        assert anonymous.sanitized_review == "A delightful change of pace."
        assert await session.scalar(
            select(func.count()).select_from(QuestionFeedbackOperation)
        ) == 0
        await enforce_feedback_retention(session, revealed_at + timedelta(days=91))
        await session.commit()
        assert await session.scalar(
            select(func.count()).select_from(AnonymousQuestionReview)
        ) == 0


async def test_wrong_or_custom_question_does_not_disclose_existence() -> None:
    member, actor, _, day = await _feedback_fixture()
    async with SessionFactory() as session:
        with pytest.raises(HTTPException) as missing:
            await put_feedback(
                session,
                member,
                actor.id,
                day.quiz_date,
                uuid4(),
                QuizFeedbackMutation(
                    operation_id=uuid4(), expected_revision=0, stars=3, tags=[]
                ),
            )
        assert missing.value.status_code == 404
