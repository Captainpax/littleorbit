"""Focused RC14 security-boundary regression tests."""

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from typing import cast
from unittest.mock import AsyncMock, Mock
from uuid import uuid4

import pytest
from fastapi import WebSocket
from pydantic import SecretStr, ValidationError

from little_orbit_api import account_entry
from little_orbit_api.admin_schemas import AdminEnrollmentStart
from little_orbit_api.config import Settings
from little_orbit_api.models import Account, AdminMfa, OneUseToken
from little_orbit_api.rate_limit import (
    RateLimitRule,
    _consume_rules,
    rate_limit_subject,
    request_rules,
)
from little_orbit_api.routes import admin as admin_routes
from little_orbit_api.routes import auth as auth_routes
from little_orbit_api.routes import notes as note_routes
from little_orbit_api.routes import notifications as notification_routes
from little_orbit_api.routes.admin import _pending_secret, _verify_factor
from little_orbit_api.routes.auth import _consume_reset_set
from little_orbit_api.routes.pairing import _eligible
from little_orbit_api.schemas import ForgotPasswordRequest, RegistrationRequest
from little_orbit_api.security import hash_token
from little_orbit_api.socket_auth import SocketIdentity


def _settings() -> Settings:
    return Settings(
        token_pepper=SecretStr("rc14-test-pepper"),
        database_url="postgresql+asyncpg://user:private-password@db/app",
    )


def test_rate_subjects_are_domain_separated_and_do_not_store_input() -> None:
    """Persist only keyed digests and keep scopes unlinkable."""

    settings = _settings()
    login = rate_limit_subject("login:subject", "person@example.test", settings)
    reset = rate_limit_subject("reset:subject", "person@example.test", settings)

    assert login != reset
    assert "person" not in login
    assert len(login) == 64


def test_rate_rules_put_ip_first_to_bound_attacker_cardinality() -> None:
    rules = request_rules(
        "login",
        "203.0.113.4",
        "person@example.test",
        ip_limit=20,
        subject_limit=5,
        window=timedelta(minutes=15),
    )

    assert [rule.scope for rule in rules] == ["login:ip", "login:subject"]


@pytest.mark.asyncio
async def test_rate_processing_stops_after_first_block(monkeypatch: pytest.MonkeyPatch) -> None:
    """A blocked IP must not allocate rows for arbitrary supplied subjects."""

    consume = AsyncMock(return_value=False)
    monkeypatch.setattr("little_orbit_api.rate_limit._consume_rule", consume)
    rules = [
        RateLimitRule("login:ip", "203.0.113.4", 1, timedelta(minutes=15)),
        RateLimitRule("login:subject", "random@example.test", 1, timedelta(minutes=15)),
    ]

    result = await _consume_rules(AsyncMock(), rules, datetime.now(UTC), _settings())

    assert not result.allowed
    assert result.blocked_scope == "login:ip"
    assert consume.await_count == 1


@pytest.mark.asyncio
async def test_duplicate_registration_still_performs_password_work(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """An insert conflict must remain neutral after the same Argon2 work."""

    password_hash = Mock(return_value="argon2-result")
    session = AsyncMock()
    session.get.return_value = None
    session.scalar.return_value = None
    monkeypatch.setattr(auth_routes, "_rate_allowed", AsyncMock(return_value=True))
    monkeypatch.setattr(account_entry, "hash_password", password_hash)
    payload = RegistrationRequest(
        email="duplicate@example.com",
        password="valid-password-123",
        display_name="Duplicate",
        is_adult=True,
        accepted_terms_version="2026-09-10",
    )

    response = await auth_routes.register(
        payload,
        client_ip="192.0.2.1",
        session=session,
        settings=_settings(),
    )

    password_hash.assert_called_once_with(payload.password)
    assert response.message == auth_routes.NEUTRAL_REGISTRATION
    session.commit.assert_not_awaited()


@pytest.mark.asyncio
async def test_unknown_recovery_routes_perform_the_neutral_password_work(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Unknown addresses must pass through the same dominant CPU work."""

    burn = Mock()
    session = AsyncMock()
    session.scalar.return_value = None
    monkeypatch.setattr(auth_routes, "_rate_allowed", AsyncMock(return_value=True))
    monkeypatch.setattr(account_entry, "burn_enumeration_work", burn)
    payload = ForgotPasswordRequest(email="missing@example.com")

    resend = await auth_routes.resend_verification(
        payload,
        client_ip="192.0.2.1",
        session=session,
        settings=_settings(),
    )
    recovery = await auth_routes.forgot_password(
        payload,
        client_ip="192.0.2.1",
        session=session,
        settings=_settings(),
    )

    assert burn.call_count == 2
    assert resend.message == auth_routes.NEUTRAL_REGISTRATION
    assert recovery.message == auth_routes.NEUTRAL_RECOVERY


def test_reset_consumes_every_outstanding_token_once() -> None:
    """A second concurrently issued link cannot survive a successful password reset."""

    now = datetime.now(UTC)
    tokens = [
        OneUseToken(
            account_id=uuid4(),
            purpose="password_reset",
            token_hash="selected",
            expires_at=now + timedelta(minutes=5),
            created_at=now,
        ),
        OneUseToken(
            account_id=uuid4(),
            purpose="password_reset",
            token_hash="other",
            expires_at=now + timedelta(minutes=5),
            created_at=now,
        ),
    ]

    assert _consume_reset_set(tokens, "selected", now)
    assert all(token.consumed_at == now for token in tokens)
    assert not _consume_reset_set(tokens, "missing", now)


def test_mfa_replacement_schema_rejects_two_current_factors() -> None:
    with pytest.raises(ValidationError):
        AdminEnrollmentStart(
            password="password",
            current_totp_code="123456",
            current_recovery_code="recovery-code-123",
        )


def test_pending_mfa_challenge_expires_without_replacing_current_factor() -> None:
    now = datetime.now(UTC)
    record = AdminMfa(
        account_id=uuid4(),
        encrypted_secret="current-factor",
        pending_encrypted_secret="new-factor",
        pending_created_at=now - timedelta(minutes=11),
        recovery_hashes=[],
        enabled_at=now - timedelta(days=1),
        created_at=now - timedelta(days=1),
        updated_at=now - timedelta(minutes=11),
    )

    assert _pending_secret(record, now, _settings()) is None
    assert record.encrypted_secret == "current-factor"


def test_recovery_proof_is_single_use_during_mfa_replacement() -> None:
    settings = _settings()
    recovery = "valid-recovery-code"
    record = AdminMfa(
        account_id=uuid4(),
        encrypted_secret="unused-for-recovery",
        recovery_hashes=[hash_token(recovery, settings.token_pepper.get_secret_value())],
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )

    assert _verify_factor(record, None, recovery, settings)
    assert not _verify_factor(record, None, recovery, settings)


@pytest.mark.asyncio
async def test_admin_configuration_is_an_explicit_safe_allowlist() -> None:
    response = await admin_routes.configuration(
        cast(Account, SimpleNamespace()), settings=_settings()
    )

    keys = set(response.values)
    assert "database_url" not in keys
    assert "session_secret" not in keys
    assert "token_pepper" not in keys
    assert response.values["database"] == "configured"
    assert all("password" not in str(value) for value in response.values.values())


def test_deleted_or_suspended_accounts_are_ineligible_for_pairing() -> None:
    active = cast(
        Account,
        SimpleNamespace(verified_at=datetime.now(UTC), suspended_at=None, deleted_at=None),
    )
    deleted = cast(
        Account,
        SimpleNamespace(
            verified_at=datetime.now(UTC), suspended_at=None, deleted_at=datetime.now(UTC)
        ),
    )

    assert _eligible(active)
    assert not _eligible(deleted)


@pytest.mark.asyncio
async def test_note_heartbeat_authorizes_session_before_note_lookup(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    session_check = AsyncMock(return_value=False)
    snapshot = AsyncMock()
    monkeypatch.setattr(note_routes, "socket_session_active", session_check)
    monkeypatch.setattr(note_routes, "_authorized_snapshot", snapshot)
    identity = SocketIdentity(uuid4(), "hashed-session")

    assert not await note_routes._socket_note_active(identity, uuid4())
    snapshot.assert_not_awaited()


@pytest.mark.asyncio
async def test_notification_heartbeat_stops_before_device_lookup(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A revoked session cannot probe or retain an installation subscription."""

    session_check = AsyncMock(return_value=False)
    session_factory = Mock(side_effect=AssertionError("device lookup must not run"))
    monkeypatch.setattr(notification_routes, "socket_session_active", session_check)
    monkeypatch.setattr(notification_routes, "SessionFactory", session_factory)
    identity = SocketIdentity(uuid4(), "hashed-session")

    assert not await notification_routes._socket_device(identity, uuid4())
    session_factory.assert_not_called()


@pytest.mark.asyncio
async def test_notification_socket_rechecks_after_hub_registration(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Revocation during registration must close before the ready hint is sent."""

    identity = SocketIdentity(uuid4(), "hashed-session")
    hub = Mock()
    websocket = SimpleNamespace(
        headers={"authorization": "Bearer opaque"},
        app=SimpleNamespace(state=SimpleNamespace(notification_connections=hub)),
        accept=AsyncMock(),
        close=AsyncMock(),
        send_json=AsyncMock(),
    )
    monkeypatch.setattr(notification_routes, "_compatible_socket", AsyncMock(return_value=True))
    monkeypatch.setattr(
        notification_routes, "authenticate_socket", AsyncMock(return_value=identity)
    )
    device_check = AsyncMock(side_effect=[True, False])
    monkeypatch.setattr(notification_routes, "_socket_device", device_check)

    await notification_routes.notification_socket(cast(WebSocket, websocket), uuid4())

    hub.add.assert_called_once()
    hub.remove.assert_called_once()
    websocket.close.assert_awaited_once_with(code=4401)
    websocket.send_json.assert_not_awaited()
