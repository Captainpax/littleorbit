"""Optional PostgreSQL proofs for device-bound owner MFA replacement."""

from __future__ import annotations

import os
import re
from datetime import UTC, datetime, timedelta
from urllib.parse import parse_qs, urlparse
from uuid import UUID, uuid4

import httpx
import pyotp
import pytest
import pytest_asyncio
from sqlalchemy import inspect, select, text

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
)
from little_orbit_api.config import get_settings  # noqa: E402
from little_orbit_api.database import Base, SessionFactory, engine  # noqa: E402
from little_orbit_api.main import create_app  # noqa: E402
from little_orbit_api.models import Account, AdminMfa, Session  # noqa: E402
from little_orbit_api.security import (  # noqa: E402
    encrypt_totp_secret,
    hash_password,
    hash_token,
)


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


def account() -> Account:
    """Create one verified owner without any relationship data."""

    now = datetime.now(UTC)
    return Account(
        id=uuid4(),
        email_normalized="admin@example.com",
        password_hash=hash_password("valid-password-123"),
        display_name="Admin",
        is_adult=True,
        accepted_terms_version="2026-09-10",
        verified_at=now,
        is_admin=True,
        created_at=now,
        updated_at=now,
    )


def admin_session(account_id: UUID, raw_token: str, *, bound: bool) -> Session:
    """Create an ordinary or MFA-verified short session for one test owner."""

    now = datetime.now(UTC)
    return Session(
        account_id=account_id,
        token_hash=hash_token(raw_token, get_settings().token_pepper.get_secret_value()),
        expires_at=now + timedelta(hours=1),
        authenticated_at=now,
        admin_mfa_verified=bound,
        created_at=now,
    )


async def seed_owner(bearer: str, recovery: str) -> tuple[UUID, UUID, str]:
    """Persist one current factor and one approved, session-bound device."""

    settings = get_settings()
    assert settings.totp_encryption_key is not None
    now = datetime.now(UTC)
    owner = account()
    active_session = admin_session(owner.id, bearer, bound=True)
    device = AdminDevice(
        account_id=owner.id,
        label="MFA replacement test device",
        public_key_spki="test-only-spki",
        key_fingerprint="a" * 64,
        approved_at=now,
        created_at=now,
    )
    current_secret = pyotp.random_base32()
    mfa = AdminMfa(
        account_id=owner.id,
        encrypted_secret=encrypt_totp_secret(
            current_secret, settings.totp_encryption_key.get_secret_value()
        ),
        recovery_hashes=[hash_token(recovery, settings.token_pepper.get_secret_value())],
        enabled_at=now,
        created_at=now,
        updated_at=now,
    )
    async with SessionFactory() as session:
        # These fixtures use explicit UUID foreign keys rather than ORM
        # relationships, so persist the parent before its dependants.
        session.add(owner)
        await session.flush()
        session.add_all([active_session, device, mfa])
        await session.flush()
        session.add(
            AdminDeviceSession(
                session_id=active_session.id,
                device_id=device.id,
                created_at=now,
            )
        )
        await session.commit()
    return owner.id, device.id, current_secret


async def start_replacement(
    client: httpx.AsyncClient, bearer: str, recovery: str
) -> httpx.Response:
    """Stage a replacement using the current recovery proof."""

    return await client.post(
        "/v2/admin/mfa/start",
        headers={"Authorization": f"Bearer {bearer}"},
        json={
            "password": "valid-password-123",
            "current_recovery_code": recovery,
        },
    )


async def test_replacement_revokes_old_sessions_and_binds_same_device() -> None:
    """A successful swap returns usable PNG/URI material and one bound session."""

    bearer = "c" * 40
    recovery = "current-recovery-code"
    _account_id, device_id, _secret = await seed_owner(bearer, recovery)
    headers = {"Authorization": f"Bearer {bearer}"}
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=create_app()), base_url="http://localhost"
    ) as client:
        rejected = await client.post(
            "/v2/admin/mfa/start",
            headers=headers,
            json={"password": "valid-password-123"},
        )
        started = await start_replacement(client, bearer, recovery)
        payload = started.json()
        secret = parse_qs(urlparse(payload["otpauth_uri"]).query)["secret"][0]
        confirmed = await client.post(
            "/v2/admin/mfa/confirm",
            headers=headers,
            json={"code": pyotp.TOTP(secret).now()},
        )
        config = await client.get(
            "/v2/admin/configuration",
            headers={"Authorization": f"Bearer {confirmed.json()['access_token']}"},
        )

    assert rejected.status_code == 422
    assert started.status_code == 200
    assert payload["qr_png_data_url"].startswith("data:image/png;base64,")
    assert payload["qr_svg_data_url"].startswith("data:image/svg+xml;base64,")
    assert confirmed.status_code == 200
    codes = confirmed.json()["recovery_codes"]
    assert len(codes) == 10
    assert all(re.fullmatch(r"[0-9a-f]{6}-[0-9a-f]{6}", code) for code in codes)
    assert config.status_code == 200
    assert all(secret_key not in config.text for secret_key in (
        "database_url", "token_pepper", "private-password"
    ))
    await assert_session_swap(bearer, confirmed.json()["access_token"], device_id)


async def assert_session_swap(bearer: str, replacement: str, device_id: UUID) -> None:
    """Verify old-token revocation and the replacement's exact device binding."""

    settings = get_settings()
    pepper = settings.token_pepper.get_secret_value()
    async with SessionFactory() as session:
        old = await session.scalar(
            select(Session).where(Session.token_hash == hash_token(bearer, pepper))
        )
        current = await session.scalar(
            select(Session).where(Session.token_hash == hash_token(replacement, pepper))
        )
        assert old is not None and old.revoked_at is not None
        assert current is not None and current.revoked_at is None
        binding = await session.get(AdminDeviceSession, current.id)
        assert binding is not None and binding.device_id == device_id


async def test_unbound_session_cannot_start_or_confirm_replacement() -> None:
    """A valid Little Orbit bearer never crosses the Big Orbit device boundary."""

    bound = "v" * 40
    unbound = "u" * 40
    recovery = "current-recovery-code"
    account_id, _device_id, _secret = await seed_owner(bound, recovery)
    async with SessionFactory() as session:
        session.add(admin_session(account_id, unbound, bound=False))
        await session.commit()
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=create_app()), base_url="http://localhost"
    ) as client:
        rejected_start = await start_replacement(client, unbound, recovery)
        started = await start_replacement(client, bound, recovery)
        secret = parse_qs(urlparse(started.json()["otpauth_uri"]).query)["secret"][0]
        rejected_confirm = await client.post(
            "/v2/admin/mfa/confirm",
            headers={"Authorization": f"Bearer {unbound}"},
            json={"code": pyotp.TOTP(secret).now()},
        )

    assert rejected_start.status_code == 403
    assert started.status_code == 200
    assert rejected_confirm.status_code == 403
