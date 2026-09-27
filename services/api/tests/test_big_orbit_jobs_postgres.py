"""Optional PostgreSQL proofs for Big Orbit job request idempotency."""

from __future__ import annotations

import asyncio
import os
from collections.abc import Awaitable, Callable
from datetime import UTC, date, datetime, timedelta
from uuid import UUID, uuid4

import httpx
import pytest
import pytest_asyncio
from sqlalchemy import func, inspect, select, text
from sqlalchemy.ext.asyncio import AsyncSession

pytestmark = [
    pytest.mark.skipif(
        not os.getenv("LITTLE_ORBIT_TEST_DATABASE_URL"),
        reason="set LITTLE_ORBIT_TEST_DATABASE_URL to an isolated PostgreSQL database",
    ),
    pytest.mark.asyncio(loop_scope="session"),
]

from little_orbit_api.admin_device_models import (  # noqa: E402
    AdminDevice,
    AdminDeviceSession,
    AdminJobRequest,
)
from little_orbit_api.config import get_settings  # noqa: E402
from little_orbit_api.database import Base, SessionFactory, engine  # noqa: E402
from little_orbit_api.main import create_app  # noqa: E402
from little_orbit_api.models import Account, Session  # noqa: E402
from little_orbit_api.routes import big_orbit_console  # noqa: E402
from little_orbit_api.security import hash_token  # noqa: E402

JobLookup = Callable[
    [AsyncSession, UUID, UUID], Awaitable[AdminJobRequest | None]
]


@pytest_asyncio.fixture(autouse=True, loop_scope="session")
async def clean_database() -> None:
    """Keep the destructive integration fixture isolated and empty per test."""

    async with engine.begin() as connection:
        existing = set(await connection.run_sync(lambda sync: inspect(sync).get_table_names()))
        quote = connection.dialect.identifier_preparer.quote
        tables = ", ".join(
            quote(table.name) for table in Base.metadata.sorted_tables if table.name in existing
        )
        await connection.execute(text(f"TRUNCATE TABLE {tables} RESTART IDENTITY CASCADE"))


async def _seed_admin(bearer: str) -> tuple[UUID, UUID]:
    """Persist one verified owner with an approved, session-bound device."""

    now = datetime.now(UTC)
    owner = Account(
        id=uuid4(),
        email_normalized="job-owner@example.com",
        password_hash="unused-by-this-test",
        display_name="Job owner",
        is_adult=True,
        accepted_terms_version="2026-09-10",
        verified_at=now,
        is_admin=True,
        created_at=now,
        updated_at=now,
    )
    active_session = Session(
        account_id=owner.id,
        token_hash=hash_token(
            bearer, get_settings().token_pepper.get_secret_value()
        ),
        expires_at=now + timedelta(hours=1),
        authenticated_at=now,
        admin_mfa_verified=True,
        created_at=now,
    )
    device = AdminDevice(
        account_id=owner.id,
        label="Job idempotency test device",
        public_key_spki="test-only-spki",
        key_fingerprint="b" * 64,
        approved_at=now,
        created_at=now,
    )
    async with SessionFactory() as session:
        session.add(owner)
        await session.flush()
        session.add_all([active_session, device])
        await session.flush()
        session.add(
            AdminDeviceSession(
                session_id=active_session.id,
                device_id=device.id,
                created_at=now,
            )
        )
        await session.commit()
    return owner.id, device.id


def _synchronize_empty_lookups(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Force two requests to race after both observe no existing operation."""

    original: JobLookup = big_orbit_console._job_for_operation
    both_ready = asyncio.Event()
    missing_count = 0

    async def synchronized_lookup(
        session: AsyncSession,
        requested_by: UUID,
        operation_id: UUID,
    ) -> AdminJobRequest | None:
        nonlocal missing_count
        record = await original(session, requested_by, operation_id)
        if record is not None:
            return record
        missing_count += 1
        if missing_count == 2:
            both_ready.set()
        await asyncio.wait_for(both_ready.wait(), timeout=5)
        return None

    monkeypatch.setattr(big_orbit_console, "_job_for_operation", synchronized_lookup)


async def _post_job(
    bearer: str,
    operation_id: UUID,
    kind: str,
    target_week: date | None = None,
) -> httpx.Response:
    payload = {"operation_id": str(operation_id), "kind": kind}
    if target_week is not None:
        payload["target_week"] = target_week.isoformat()
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=create_app()), base_url="http://localhost"
    ) as client:
        return await client.post(
            "/v2/admin/jobs",
            headers={"Authorization": f"Bearer {bearer}"},
            json=payload,
        )


async def test_concurrent_identical_requests_return_one_persisted_job(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    bearer = "j" * 40
    owner_id, device_id = await _seed_admin(bearer)
    operation_id = uuid4()
    _synchronize_empty_lookups(monkeypatch)

    responses = await asyncio.gather(
        _post_job(bearer, operation_id, "backup"),
        _post_job(bearer, operation_id, "backup"),
    )

    assert [response.status_code for response in responses] == [200, 200]
    assert responses[0].json() == responses[1].json()
    async with SessionFactory() as session:
        records = list(await session.scalars(select(AdminJobRequest)))
    assert len(records) == 1
    assert records[0].requested_by == owner_id
    assert records[0].requested_device_id == device_id
    assert str(records[0].id) == responses[0].json()["id"]


async def test_concurrent_conflicting_payloads_reject_the_loser(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    bearer = "k" * 40
    await _seed_admin(bearer)
    operation_id = uuid4()
    _synchronize_empty_lookups(monkeypatch)

    responses = await asyncio.gather(
        _post_job(bearer, operation_id, "backup"),
        _post_job(bearer, operation_id, "test_restore"),
    )

    assert sorted(response.status_code for response in responses) == [200, 409]
    accepted = next(response for response in responses if response.status_code == 200)
    rejected = next(response for response in responses if response.status_code == 409)
    assert rejected.json() == {"detail": "Operation ID was already used"}
    async with SessionFactory() as session:
        records = list(await session.scalars(select(AdminJobRequest)))
    assert len(records) == 1
    assert records[0].kind == accepted.json()["kind"]


async def test_retry_returns_current_result_and_conflict_stays_rejected() -> None:
    bearer = "m" * 40
    await _seed_admin(bearer)
    operation_id = uuid4()
    target_week = date(2026, 9, 28)
    created = await _post_job(
        bearer, operation_id, "generate_quizzes", target_week
    )
    assert created.status_code == 200

    finished_at = datetime.now(UTC)
    async with SessionFactory() as session:
        record = await session.scalar(
            select(AdminJobRequest).where(AdminJobRequest.operation_id == operation_id)
        )
        assert record is not None
        record.status = "passed"
        record.result_json = {"outcome": "verified"}
        record.finished_at = finished_at
        await session.commit()

    replayed = await _post_job(
        bearer, operation_id, "generate_quizzes", target_week
    )
    conflicted = await _post_job(
        bearer, operation_id, "generate_quizzes", date(2026, 10, 5)
    )

    assert replayed.status_code == 200
    assert replayed.json()["id"] == created.json()["id"]
    assert replayed.json()["status"] == "passed"
    assert replayed.json()["result"] == {"outcome": "verified"}
    assert conflicted.status_code == 409
    async with SessionFactory() as session:
        count = await session.scalar(select(func.count()).select_from(AdminJobRequest))
    assert count == 1
