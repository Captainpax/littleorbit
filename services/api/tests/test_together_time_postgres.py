"""Isolated PostgreSQL regressions for concurrent together-time ingestion."""

import asyncio
import os
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

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

from little_orbit_api.clock import SystemClock  # noqa: E402
from little_orbit_api.database import Base, SessionFactory, engine  # noqa: E402
from little_orbit_api.models import (  # noqa: E402
    Account,
    Couple,
    CoupleMember,
    LocationSample,
    TogetherBucket,
)
from little_orbit_api.routes.together_time_v2 import upload_locations_v2  # noqa: E402
from little_orbit_api.schemas import (  # noqa: E402
    LocationBatchRequest,
    LocationBatchV2Response,
    LocationSampleRequest,
)
from little_orbit_api.together_models import TogetherDay  # noqa: E402


@pytest_asyncio.fixture(autouse=True, loop_scope="session")
async def clean_database() -> None:
    """Keep all destructive operations in the explicitly selected test database."""

    async with engine.begin() as connection:
        existing = set(await connection.run_sync(lambda sync: inspect(sync).get_table_names()))
        quote = connection.dialect.identifier_preparer.quote
        tables = ", ".join(
            quote(table.name) for table in Base.metadata.sorted_tables if table.name in existing
        )
        await connection.execute(text(f"TRUNCATE TABLE {tables} RESTART IDENTITY CASCADE"))


async def test_concurrent_upload_retry_and_restart_are_deterministic() -> None:
    pair, left, right = await _pair()
    now = SystemClock().now().astimezone(UTC).replace(second=0, microsecond=0)
    initial_left = _sample(now - timedelta(minutes=4), 45.5000)
    initial_right = _sample(now - timedelta(minutes=4), 45.5001)
    await _upload(left, pair.id, initial_left)
    await _upload(right, pair.id, initial_right)

    next_left = _sample(now - timedelta(minutes=2), 45.5000)
    next_right = _sample(now - timedelta(minutes=2), 45.5001)
    left_result, right_result = await asyncio.gather(
        _upload(left, pair.id, next_left),
        _upload(right, pair.id, next_right),
    )
    retry = await _upload(left, pair.id, next_left)

    assert left_result.accepted == 1
    assert right_result.accepted == 1
    assert retry.accepted == 0
    assert retry.duplicates == 1
    async with SessionFactory() as restarted_session:
        total = await restarted_session.scalar(
            select(func.coalesce(func.sum(TogetherBucket.duration_seconds), 0)).where(
                TogetherBucket.couple_id == pair.id
            )
        )
        samples = await restarted_session.scalar(
            select(func.count()).select_from(LocationSample).where(
                LocationSample.couple_id == pair.id
            )
        )
        day = await restarted_session.scalar(
            select(TogetherDay).where(
                TogetherDay.couple_id == pair.id,
                TogetherDay.day == next_left.recorded_at.astimezone(UTC).date(),
            )
        )

    assert total == 120
    assert samples == 4
    assert day is not None and day.estimated_seconds == 120
    assert day.estimate_method == "current_v3"


async def test_same_sample_identity_with_changed_payload_is_rejected() -> None:
    pair, left, _ = await _pair()
    sample = _sample(SystemClock().now().astimezone(UTC) - timedelta(minutes=1), 45.5)
    await _upload(left, pair.id, sample)
    changed = LocationSampleRequest(
        sample_id=sample.sample_id,
        recorded_at=sample.recorded_at,
        latitude=46.0,
        longitude=sample.longitude,
        accuracy_m=sample.accuracy_m,
    )

    with pytest.raises(HTTPException) as failure:
        await _upload(left, pair.id, changed)

    assert failure.value.status_code == 409


async def _upload(
    actor: Account, relationship_id: UUID, sample: LocationSampleRequest
) -> LocationBatchV2Response:
    async with SessionFactory() as session:
        return await upload_locations_v2(
            LocationBatchRequest(relationship_id=relationship_id, samples=[sample]),
            actor,
            session,
        )


async def _pair() -> tuple[Couple, Account, Account]:
    now = SystemClock().now().astimezone(UTC)
    left = _account("left", now)
    right = _account("right", now)
    pair = Couple(
        id=uuid4(),
        proximity_threshold_m=100,
        proximity_algorithm_version=2,
        home_timezone="America/Los_Angeles",
        created_at=now - timedelta(days=2),
        updated_at=now,
    )
    members = [
        CoupleMember(
            id=uuid4(), couple_id=pair.id, account_id=account.id,
            joined_at=pair.created_at, intimacy_enabled=False, location_enabled=True,
        )
        for account in (left, right)
    ]
    async with SessionFactory() as session:
        session.add_all([left, right, pair, *members])
        await session.commit()
    return pair, left, right


def _account(prefix: str, now: datetime) -> Account:
    return Account(
        id=uuid4(),
        email_normalized=f"{prefix}-{uuid4()}@example.com",
        password_hash="unused",
        display_name=prefix.title(),
        is_adult=True,
        accepted_terms_version="2026-09-10",
        verified_at=now,
        is_admin=False,
        created_at=now,
        updated_at=now,
    )


def _sample(recorded_at: datetime, latitude: float) -> LocationSampleRequest:
    return LocationSampleRequest(
        sample_id=uuid4(),
        recorded_at=recorded_at,
        latitude=latitude,
        longitude=-122.6,
        accuracy_m=8,
    )
