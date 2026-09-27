"""Optional PostgreSQL coverage for AI queue ordering and token fencing."""

import os
from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta

import pytest
import pytest_asyncio
from sqlalchemy import select, text

pytestmark = [
    pytest.mark.skipif(
        not os.getenv("LITTLE_ORBIT_TEST_DATABASE_URL"),
        reason="set LITTLE_ORBIT_TEST_DATABASE_URL to an isolated PostgreSQL database",
    ),
    pytest.mark.asyncio(loop_scope="session"),
]

from little_orbit_api.ai_work_queue import (  # noqa: E402
    WEEKLY_GENERATION,
    WEEKLY_LEARNING,
    claim_due_work,
    complete_work,
    defer_due_work,
    enqueue_due_weekly_work,
    heartbeat_work,
    retry_work,
)
from little_orbit_api.config import Settings  # noqa: E402
from little_orbit_api.database import SessionFactory, engine  # noqa: E402
from little_orbit_api.models import Question  # noqa: E402
from little_orbit_api.quiz_generation_pool_service import (  # noqa: E402
    _clear_replaceable_pool,
)
from little_orbit_api.quiz_intelligence_models import (  # noqa: E402
    AiRun,
    AiWorkItem,
    QuizWeekPlan,
)
from little_orbit_api.quiz_theme_service import (  # noqa: E402
    _fallback_plan,
    _persist_plan,
)


@pytest_asyncio.fixture(autouse=True, loop_scope="session")
async def clean_database() -> AsyncIterator[None]:
    async with engine.begin() as connection:
        await connection.execute(text("TRUNCATE TABLE ai_work_queue"))
        await connection.execute(
            text("DELETE FROM ai_runs WHERE run_key = 'generate:2026-09-28'")
        )
        await connection.execute(
            text("DELETE FROM quiz_day_themes WHERE local_date BETWEEN '2035-01-01' AND '2035-01-07'")
        )
        await connection.execute(
            text("DELETE FROM quiz_week_plans WHERE week_start = '2035-01-01'")
        )
        await connection.execute(
            text("DELETE FROM questions WHERE publish_date = '2040-01-01'")
        )
    yield
    async with engine.begin() as connection:
        await connection.execute(text("TRUNCATE TABLE ai_work_queue"))
        await connection.execute(
            text("DELETE FROM ai_runs WHERE run_key = 'generate:2026-09-28'")
        )
        await connection.execute(
            text("DELETE FROM quiz_day_themes WHERE local_date BETWEEN '2035-01-01' AND '2035-01-07'")
        )
        await connection.execute(
            text("DELETE FROM quiz_week_plans WHERE week_start = '2035-01-01'")
        )
        await connection.execute(
            text("DELETE FROM questions WHERE publish_date = '2040-01-01'")
        )


async def test_oldest_due_work_retries_in_six_hours_and_fences_stale_token() -> None:
    now = datetime(2026, 9, 27, 10, tzinfo=UTC)
    async with SessionFactory() as session:
        session.add_all(
            [
                AiWorkItem(
                    kind=WEEKLY_LEARNING,
                    scheduled_at=now - timedelta(days=1),
                    next_attempt_at=now - timedelta(days=1),
                    attempt_count=0,
                ),
                AiWorkItem(
                    kind=WEEKLY_GENERATION,
                    scheduled_at=now,
                    next_attempt_at=now,
                    attempt_count=0,
                ),
            ]
        )
        await session.commit()

    lease = await claim_due_work(
        now,
        stale_after=timedelta(hours=2),
        minimum_gap=timedelta(hours=6),
    )
    assert lease is not None and lease.kind == WEEKLY_LEARNING
    assert not await heartbeat_work(
        lease.__class__(lease.id, lease.kind, lease.scheduled_at, lease.id), now
    )
    assert await retry_work(lease, now, timedelta(hours=6))
    assert (
        await claim_due_work(
            now + timedelta(hours=5),
            stale_after=timedelta(hours=2),
            minimum_gap=timedelta(hours=6),
        )
        is None
    )

    retried = await claim_due_work(
        now + timedelta(hours=6),
        stale_after=timedelta(hours=2),
        minimum_gap=timedelta(hours=6),
    )
    assert retried is not None and retried.id == lease.id
    assert not await complete_work(lease, now + timedelta(hours=6))
    assert await complete_work(retried, now + timedelta(hours=6))
    async with SessionFactory() as session:
        record = await session.scalar(select(AiWorkItem).where(AiWorkItem.id == lease.id))
    assert record is not None
    assert record.next_attempt_at is None
    assert record.attempt_count == 2


async def test_gpu_contention_cannot_let_newer_work_overtake_oldest() -> None:
    now = datetime(2026, 9, 27, 10, tzinfo=UTC)
    async with SessionFactory() as session:
        session.add_all(
            [
                AiWorkItem(
                    kind=WEEKLY_LEARNING,
                    scheduled_at=now - timedelta(days=1),
                    next_attempt_at=now,
                    attempt_count=0,
                ),
                AiWorkItem(
                    kind=WEEKLY_GENERATION,
                    scheduled_at=now,
                    next_attempt_at=now,
                    attempt_count=0,
                ),
            ]
        )
        await session.commit()

    assert await defer_due_work(now, timedelta(hours=6))
    assert (
        await claim_due_work(
            now + timedelta(hours=1),
            stale_after=timedelta(hours=2),
            minimum_gap=timedelta(hours=6),
        )
        is None
    )
    lease = await claim_due_work(
        now + timedelta(hours=6),
        stale_after=timedelta(hours=2),
        minimum_gap=timedelta(hours=6),
    )
    assert lease is not None and lease.kind == WEEKLY_LEARNING


async def test_completed_legacy_generation_does_not_consume_first_queue_slot() -> None:
    now = datetime(2026, 9, 28, 12, tzinfo=UTC)
    async with SessionFactory() as session:
        session.add(
            AiRun(
                run_key="generate:2026-09-28",
                kind="generation",
                status="passed",
                summary_json={},
                started_at=now - timedelta(days=1),
                finished_at=now - timedelta(days=1),
            )
        )
        await session.commit()

    await enqueue_due_weekly_work(now, Settings())

    async with SessionFactory() as session:
        records = list(
            await session.scalars(
                select(AiWorkItem).order_by(AiWorkItem.scheduled_at)
            )
        )
    generation = next(item for item in records if item.kind == WEEKLY_GENERATION)
    learning = next(item for item in records if item.kind == WEEKLY_LEARNING)
    assert generation.next_attempt_at is None
    assert learning.next_attempt_at is not None


async def test_stale_token_cannot_commit_a_theme_plan_result() -> None:
    """The queue row is fenced inside the transaction that writes AI output."""

    now = datetime(2035, 1, 6, 10, tzinfo=UTC)
    async with SessionFactory() as session:
        session.add(
            AiWorkItem(
                kind=WEEKLY_LEARNING,
                scheduled_at=now,
                next_attempt_at=now,
                attempt_count=0,
            )
        )
        await session.commit()
    stale = await claim_due_work(
        now,
        stale_after=timedelta(hours=2),
        minimum_gap=timedelta(0),
    )
    assert stale is not None
    assert await retry_work(stale, now, timedelta(0))
    current = await claim_due_work(
        now,
        stale_after=timedelta(hours=2),
        minimum_gap=timedelta(0),
    )
    assert current is not None and current.id == stale.id
    plan = _fallback_plan(datetime(2035, 1, 1, tzinfo=UTC).date())

    with pytest.raises(RuntimeError, match="expired before result commit"):
        await _persist_plan(
            plan,
            "America/Los_Angeles",
            "en-US",
            "stale-fence-test",
            stale,
        )
    async with SessionFactory() as session:
        assert await session.scalar(
            select(QuizWeekPlan.id).where(QuizWeekPlan.week_start == plan.week_start)
        ) is None

    await _persist_plan(
        plan,
        "America/Los_Angeles",
        "en-US",
        "current-fence-test",
        current,
    )
    async with SessionFactory() as session:
        assert await session.scalar(
            select(QuizWeekPlan.id).where(QuizWeekPlan.week_start == plan.week_start)
        ) is not None


async def test_pool_delete_rolls_back_when_successor_write_fails() -> None:
    target = datetime(2040, 1, 1, tzinfo=UTC).date()
    original = Question(
        publish_date=target,
        kind="free_text",
        prompt="What calm moment would you like to revisit together?",
        category="memories",
        intimacy=False,
        options=[],
        option_icons=[],
        interaction_version=2,
        display_order=1,
        surprise=True,
        source="curated",
        normalized_hash="a" * 64,
    )
    async with SessionFactory() as session:
        session.add(original)
        await session.commit()
        original_id = original.id

    async with SessionFactory() as session:
        assert await _clear_replaceable_pool(session, target)
        await session.rollback()  # Simulate successor validation or insert failure.

    async with SessionFactory() as session:
        assert await session.get(Question, original_id) is not None
