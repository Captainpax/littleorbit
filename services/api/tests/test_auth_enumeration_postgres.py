"""PostgreSQL races for enumeration-resistant account entry points."""

import asyncio
import os
from datetime import UTC, datetime
from uuid import uuid4

import httpx
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
from little_orbit_api.main import create_app  # noqa: E402
from little_orbit_api.models import Account, MailOutbox, OneUseToken  # noqa: E402
from little_orbit_api.security import hash_password  # noqa: E402


@pytest_asyncio.fixture(autouse=True, loop_scope="session")
async def clean_database() -> None:
    """Keep these destructive race checks inside the named isolated database."""

    async with engine.begin() as connection:
        existing = set(await connection.run_sync(lambda sync: inspect(sync).get_table_names()))
        quote = connection.dialect.identifier_preparer.quote
        tables = ", ".join(
            quote(table.name) for table in Base.metadata.sorted_tables if table.name in existing
        )
        await connection.execute(text(f"TRUNCATE TABLE {tables} RESTART IDENTITY CASCADE"))


def _account(email: str, *, verified: bool) -> Account:
    now = datetime.now(UTC)
    return Account(
        id=uuid4(),
        email_normalized=email,
        password_hash=hash_password("valid-password-123"),
        display_name="Test account",
        is_adult=True,
        accepted_terms_version="2026-09-10",
        verified_at=now if verified else None,
        is_admin=False,
        created_at=now,
        updated_at=now,
    )


async def _post_twice(
    path: str, payload: dict[str, object]
) -> tuple[httpx.Response, httpx.Response]:
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=create_app()), base_url="http://localhost"
    ) as client:
        return await asyncio.gather(
            client.post(path, json=payload),
            client.post(path, json=payload),
        )


async def _assert_one_token_and_mail() -> None:
    async with SessionFactory() as session:
        assert await session.scalar(select(func.count()).select_from(OneUseToken)) == 1
        assert await session.scalar(select(func.count()).select_from(MailOutbox)) == 1


async def test_concurrent_registration_is_neutral_and_creates_one_account() -> None:
    """A duplicate insert race must not reveal itself as a server error."""

    responses = await _post_twice(
        "/v1/auth/register",
        {
            "email": "new-account@example.com",
            "password": "valid-password-123",
            "display_name": "New account",
            "is_adult": True,
            "accepted_terms_version": "2026-09-10",
            "website": "",
        },
    )

    assert [response.status_code for response in responses] == [202, 202]
    assert responses[0].json() == responses[1].json()
    async with SessionFactory() as session:
        assert await session.scalar(select(func.count()).select_from(Account)) == 1
    await _assert_one_token_and_mail()


async def test_concurrent_verification_resends_obey_one_cooldown() -> None:
    """The account lock must turn simultaneous resend attempts into one email."""

    account = _account("unverified@example.com", verified=False)
    async with SessionFactory() as session:
        session.add(account)
        await session.commit()
    responses = await _post_twice(
        "/v1/auth/resend-verification", {"email": account.email_normalized}
    )

    assert [response.status_code for response in responses] == [202, 202]
    assert responses[0].json() == responses[1].json()
    await _assert_one_token_and_mail()


async def test_concurrent_recovery_requests_issue_one_current_link() -> None:
    """The account lock must keep simultaneous recovery requests from racing links."""

    account = _account("recover-once@example.com", verified=True)
    async with SessionFactory() as session:
        session.add(account)
        await session.commit()
    responses = await _post_twice("/v1/auth/forgot-password", {"email": account.email_normalized})

    assert [response.status_code for response in responses] == [202, 202]
    assert responses[0].json() == responses[1].json()
    await _assert_one_token_and_mail()
