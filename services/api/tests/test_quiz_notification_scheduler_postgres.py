"""PostgreSQL integration checks for scheduled daily quiz alerts."""

import asyncio
import os
from datetime import UTC, datetime

import pytest
import pytest_asyncio
from sqlalchemy import func, inspect, select, text

pytestmark = [
    pytest.mark.skipif(
        not os.getenv("LITTLE_ORBIT_TEST_DATABASE_URL"),
        reason="set LITTLE_ORBIT_TEST_DATABASE_URL to an isolated PostgreSQL database",
    ),
    pytest.mark.asyncio(loop_scope="session"),
]

from little_orbit_api.database import Base, SessionFactory, engine  # noqa: E402
from little_orbit_api.models import Account, Couple, CoupleMember, Question  # noqa: E402
from little_orbit_api.notification_models import NotificationEvent  # noqa: E402
from little_orbit_api.quiz_notification_scheduler import _notify_couple  # noqa: E402
from little_orbit_api.quiz_v2_service import utc_today  # noqa: E402


@pytest_asyncio.fixture(autouse=True, loop_scope="session")
async def clean_database() -> None:
    """Keep the scheduling race check inside the named disposable database."""

    async with engine.begin() as connection:
        existing = set(await connection.run_sync(lambda sync: inspect(sync).get_table_names()))
        quote = connection.dialect.identifier_preparer.quote
        tables = ", ".join(
            quote(table.name) for table in Base.metadata.sorted_tables if table.name in existing
        )
        await connection.execute(text(f"TRUNCATE TABLE {tables} RESTART IDENTITY CASCADE"))


def _account(email: str, now: datetime) -> Account:
    return Account(
        email_normalized=email,
        password_hash="unused-in-scheduler-test",
        display_name=email.split("@", 1)[0],
        is_adult=True,
        accepted_terms_version="2026-09-10",
        verified_at=now,
        is_admin=False,
        created_at=now,
        updated_at=now,
    )


async def _seed_daily_pool() -> Couple:
    now = datetime.now(UTC)
    couple = Couple(
        proximity_threshold_m=100,
        proximity_algorithm_version=2,
        home_timezone="America/Los_Angeles",
        created_at=now,
        updated_at=now,
    )
    members = [_account("scheduler-one@example.com", now), _account("scheduler-two@example.com", now)]
    questions = [
        Question(
            publish_date=utc_today(),
            kind="free_text",
            prompt=f"Safe scheduled question {position}?",
            category="everyday",
            intimacy=False,
            options=[],
            option_icons=[],
            interaction_version=2,
            display_order=position,
            surprise=False,
            source="curated",
            normalized_hash=f"{position:064x}",
        )
        for position in range(1, 6)
    ]
    async with SessionFactory() as session:
        session.add_all([*members, couple, *questions])
        await session.flush()
        session.add_all(
            [
                CoupleMember(
                    couple_id=couple.id,
                    account_id=member.id,
                    joined_at=now,
                    intimacy_enabled=False,
                    location_enabled=False,
                )
                for member in members
            ]
        )
        await session.commit()
    return couple


async def test_concurrent_scheduler_creates_one_alert_per_member() -> None:
    """Overlapping worker ticks serialize on the couple and never duplicate alerts."""

    couple = await _seed_daily_pool()
    results = await asyncio.gather(
        _notify_couple(couple.id, utc_today()),
        _notify_couple(couple.id, utc_today()),
    )

    async with SessionFactory() as session:
        count = await session.scalar(
            select(func.count())
            .select_from(NotificationEvent)
            .where(NotificationEvent.kind == "quiz_available")
        )
        recipients = set(
            await session.scalars(
                select(NotificationEvent.recipient_id).where(
                    NotificationEvent.kind == "quiz_available"
                )
            )
        )

    assert sorted(results) == [0, 2]
    assert count == 2
    assert len(recipients) == 2
