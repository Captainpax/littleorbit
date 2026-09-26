"""PostgreSQL checks for the hard raw-coordinate retention boundary."""

import os
from datetime import UTC, datetime, timedelta
from uuid import uuid4

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
from little_orbit_api.maintenance import purge_expired_location_samples  # noqa: E402
from little_orbit_api.models import Account, Couple, CoupleMember, LocationSample  # noqa: E402


@pytest_asyncio.fixture(autouse=True, loop_scope="session")
async def clean_database() -> None:
    """Keep destructive retention checks inside the explicitly named test database."""

    async with engine.begin() as connection:
        existing = set(await connection.run_sync(lambda sync: inspect(sync).get_table_names()))
        quote = connection.dialect.identifier_preparer.quote
        tables = ", ".join(
            quote(table.name) for table in Base.metadata.sorted_tables if table.name in existing
        )
        await connection.execute(text(f"TRUNCATE TABLE {tables} RESTART IDENTITY CASCADE"))


async def test_purge_defends_absolute_ceiling_when_declared_expiry_is_wrong() -> None:
    now = datetime(2026, 9, 14, 12, tzinfo=UTC)
    account = Account(
        id=uuid4(),
        email_normalized="location-retention@example.com",
        password_hash="unused",
        display_name="Retention",
        is_adult=True,
        accepted_terms_version="2026-09-10",
        verified_at=now,
        is_admin=False,
        created_at=now,
        updated_at=now,
    )
    couple = Couple(
        id=uuid4(),
        proximity_threshold_m=100,
        home_timezone="America/Los_Angeles",
        created_at=now,
        updated_at=now,
    )
    member = CoupleMember(
        id=uuid4(),
        couple_id=couple.id,
        account_id=account.id,
        joined_at=now,
        intimacy_enabled=False,
        location_enabled=True,
    )
    overdue = _sample(account, couple, now - timedelta(hours=24, seconds=1), now + timedelta(days=1))
    declared_expired = _sample(account, couple, now - timedelta(hours=1), now)
    fresh = _sample(account, couple, now - timedelta(minutes=5), now + timedelta(hours=1))
    async with SessionFactory() as session:
        session.add_all([account, couple, member, overdue, declared_expired, fresh])
        await session.commit()
        await purge_expired_location_samples(session, now)
        await session.commit()
        remaining = await session.scalar(select(func.count()).select_from(LocationSample))
        remaining_id = await session.scalar(select(LocationSample.sample_id))

    assert remaining == 1
    assert remaining_id == fresh.sample_id


def _sample(
    account: Account,
    couple: Couple,
    recorded_at: datetime,
    expires_at: datetime,
) -> LocationSample:
    """Build one raw sample for retention boundary checks."""

    return LocationSample(
        id=uuid4(),
        sample_id=uuid4(),
        account_id=account.id,
        couple_id=couple.id,
        recorded_at=recorded_at,
        latitude=45.5,
        longitude=-122.6,
        accuracy_m=5,
        expires_at=expires_at,
    )
