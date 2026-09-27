"""Optional PostgreSQL proof for reserve synchronization and atomic use."""

import os
from datetime import date

import pytest
import pytest_asyncio
from sqlalchemy import inspect, text

pytestmark = [
    pytest.mark.skipif(
        not os.getenv("LITTLE_ORBIT_TEST_DATABASE_URL"),
        reason="set LITTLE_ORBIT_TEST_DATABASE_URL to an isolated PostgreSQL database",
    ),
    pytest.mark.asyncio(loop_scope="session"),
]

from little_orbit_api.database import Base, SessionFactory, engine  # noqa: E402
from little_orbit_api.quiz_reserve_service import (  # noqa: E402
    available_reserve,
    consume_selected_reserve,
    reserve_health,
    sync_question_reserve,
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


async def test_sync_and_consume_are_complete_and_atomic() -> None:
    health = await sync_question_reserve()
    assert health.general_available == 1_825
    assert health.intimacy_available == 365
    candidates = await available_reserve()
    general = next(item for item in candidates if not item.intimacy)
    intimacy = next(item for item in candidates if item.intimacy)
    async with SessionFactory() as session:
        await consume_selected_reserve(session, date.today(), [general, intimacy])
        await session.commit()
    remaining = await reserve_health()
    assert remaining.general_available == 1_824
    assert remaining.intimacy_available == 364
    async with SessionFactory() as session:
        with pytest.raises(RuntimeError, match="already consumed"):
            await consume_selected_reserve(session, date.today(), [general])
