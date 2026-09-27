"""One-use PIN bootstrap isolated from ordinary Big Orbit administrator sessions."""

import hmac
import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta
from uuid import UUID

import pyotp
from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from .admin_device_models import (
    AdminBootstrapCredential,
    AdminBootstrapSession,
    AdminDevice,
)
from .big_orbit_auth import approve_device, create_enrollment_device, issue_device_session
from .big_orbit_schemas import (
    BootstrapCompletion,
    BootstrapMfaEnrollment,
    BootstrapStatusResponse,
)
from .clock import SystemClock
from .config import Settings
from .models import Account, AdminMfa, SecurityEvent, Session
from .security import (
    decrypt_totp_secret,
    encrypt_totp_secret,
    hash_password,
    hash_token,
    new_opaque_token,
    new_recovery_codes,
    qr_png_data_url,
    totp_uri,
    verify_password,
    verify_totp,
)

BOOTSTRAP_LIFETIME = timedelta(minutes=10)
PIN_ATTEMPT_LIMIT = 5
_DUMMY_PASSWORD_HASH = hash_password("timing-only-bootstrap-password")


@dataclass(frozen=True)
class StartedBootstrap:
    """Raw setup token and persisted bootstrap/device identities."""

    token: str
    record: AdminBootstrapSession
    account: Account
    device: AdminDevice


def new_bootstrap_pin() -> str:
    """Create an eight-digit terminal-only PIN using a cryptographic generator."""

    return f"{secrets.randbelow(100_000_000):08d}"


async def issue_bootstrap_pin(
    session: AsyncSession, account: Account, settings: Settings
) -> str:
    """Invalidate older setup capabilities and persist only the new PIN digest."""

    now = SystemClock().now()
    prior_credentials = await session.scalars(
        select(AdminBootstrapCredential)
        .where(
            AdminBootstrapCredential.account_id == account.id,
            AdminBootstrapCredential.consumed_at.is_(None),
            AdminBootstrapCredential.invalidated_at.is_(None),
        )
        .with_for_update()
    )
    for credential in prior_credentials:
        credential.invalidated_at = now
    prior_sessions = list(
        await session.scalars(
            select(AdminBootstrapSession)
            .where(
                AdminBootstrapSession.account_id == account.id,
                AdminBootstrapSession.expires_at > now,
            )
            .with_for_update()
        )
    )
    for setup in prior_sessions:
        setup.expires_at = now
        if setup.completed_at is None:
            setup.completed_at = now
        device = await session.get(AdminDevice, setup.device_id, with_for_update=True)
        if device is not None and device.approved_at is None:
            device.revoked_at = now
    pin = new_bootstrap_pin()
    session.add(
        AdminBootstrapCredential(
            account_id=account.id,
            pin_hash=_pin_digest(pin, settings),
            failed_attempts=0,
            expires_at=now + BOOTSTRAP_LIFETIME,
            created_at=now,
        )
    )
    return pin


async def start_bootstrap(
    session: AsyncSession,
    email: str,
    password: str,
    pin: str,
    label: str,
    public_key_spki: str,
    settings: Settings,
) -> StartedBootstrap:
    """Consume one PIN and issue a restricted setup token after password verification."""

    account = await _verified_admin(session, email, password)
    now = SystemClock().now()
    credential = await _consume_pin(session, account, pin, settings, now)
    credential.consumed_at = now
    device = await create_enrollment_device(session, account, label, public_key_spki)
    mfa = await session.get(AdminMfa, account.id, with_for_update=True)
    mfa_required = mfa is None or mfa.enabled_at is None
    if mfa_required:
        _stage_mfa(session, account, mfa, settings, now)
    raw = new_opaque_token(48)
    record = AdminBootstrapSession(
        account_id=account.id,
        device_id=device.id,
        token_hash=hash_token(raw, settings.token_pepper.get_secret_value()),
        mfa_required=mfa_required,
        expires_at=now + BOOTSTRAP_LIFETIME,
        created_at=now,
    )
    session.add(record)
    await session.flush()
    session.add(_event(account.id, "big_orbit_bootstrap", "pin_consumed"))
    return StartedBootstrap(raw, record, account, device)


async def _verified_admin(
    session: AsyncSession, email: str, password: str
) -> Account:
    """Resolve the owner without changing the neutral bootstrap failure response."""

    account = await session.scalar(
        select(Account)
        .where(Account.email_normalized == email)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    stored_hash = account.password_hash if account is not None else _DUMMY_PASSWORD_HASH
    if not verify_password(stored_hash, password) or not _active_admin(account):
        raise _invalid_bootstrap()
    assert account is not None
    return account


async def _consume_pin(
    session: AsyncSession,
    account: Account,
    pin: str,
    settings: Settings,
    now: datetime,
) -> AdminBootstrapCredential:
    """Lock one current credential and persist every bounded failed attempt."""

    credential = await session.scalar(
        select(AdminBootstrapCredential)
        .where(
            AdminBootstrapCredential.account_id == account.id,
            AdminBootstrapCredential.consumed_at.is_(None),
            AdminBootstrapCredential.invalidated_at.is_(None),
        )
        .order_by(AdminBootstrapCredential.created_at.desc())
        .with_for_update()
    )
    if credential is None:
        await session.commit()
        raise _invalid_bootstrap()
    valid = (
        credential.expires_at > now
        and credential.failed_attempts < PIN_ATTEMPT_LIMIT
        and hmac.compare_digest(credential.pin_hash, _pin_digest(pin, settings))
    )
    if not valid:
        credential.failed_attempts = min(PIN_ATTEMPT_LIMIT, credential.failed_attempts + 1)
        if credential.failed_attempts == PIN_ATTEMPT_LIMIT:
            credential.invalidated_at = now
        await session.commit()
        raise _invalid_bootstrap()
    return credential


async def bootstrap_principal(
    session: AsyncSession,
    raw_token: str,
    settings: Settings,
    *,
    allow_completed: bool = False,
) -> tuple[AdminBootstrapSession, Account, AdminDevice]:
    """Resolve a restricted setup token without accepting an ordinary admin bearer."""

    digest = hash_token(raw_token, settings.token_pepper.get_secret_value())
    setup = await session.scalar(
        select(AdminBootstrapSession)
        .where(AdminBootstrapSession.token_hash == digest)
        .with_for_update()
    )
    now = SystemClock().now()
    completed = setup is not None and setup.completed_at is not None
    if setup is None or (completed and not allow_completed) or setup.expires_at <= now:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Bootstrap session is unavailable")
    account = await session.get(Account, setup.account_id, with_for_update=True)
    device = await session.get(AdminDevice, setup.device_id, with_for_update=True)
    if not _active_admin(account) or account is None or device is None or device.revoked_at:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Bootstrap session is unavailable")
    return setup, account, device


async def bootstrap_status(
    session: AsyncSession,
    setup: AdminBootstrapSession,
    account: Account,
    settings: Settings,
) -> BootstrapStatusResponse:
    """Render resumable setup state and QR material only after device proof."""

    enrollment = None
    if setup.device_confirmed_at is not None and setup.mfa_required:
        enrollment = await _mfa_enrollment(session, account, settings)
    return BootstrapStatusResponse(
        expires_at=setup.expires_at,
        account_id=account.id,
        device_id=setup.device_id,
        device_confirmed=setup.device_confirmed_at is not None,
        mfa_required=setup.mfa_required,
        mfa_enrollment=enrollment,
    )


async def complete_bootstrap(
    session: AsyncSession,
    setup: AdminBootstrapSession,
    account: Account,
    device: AdminDevice,
    settings: Settings,
    recovery_codes: list[str] | None = None,
) -> BootstrapCompletion:
    """Approve a proven key, or safely reissue credentials after a lost response."""

    if setup.device_confirmed_at is None:
        raise HTTPException(status.HTTP_409_CONFLICT, "Bootstrap is not ready")
    recovering = setup.completed_at is not None
    device_credential, credential_expiry = approve_device(device, settings)
    issued = await issue_device_session(session, account, device, settings)
    if not recovering:
        setup.completed_at = SystemClock().now()
    outcome = "bootstrap_recovered" if recovering else "bootstrap_enrolled"
    session.add(_event(account.id, "big_orbit_device", outcome))
    return BootstrapCompletion(
        access_token=issued.token,
        expires_at=issued.expires_at,
        account_id=account.id,
        device_id=device.id,
        device_credential=device_credential,
        credential_expires_at=credential_expiry,
        recovery_codes=recovery_codes or [],
    )


async def enable_bootstrap_mfa(
    session: AsyncSession,
    setup: AdminBootstrapSession,
    account: Account,
    code: str,
    settings: Settings,
) -> list[str]:
    """Enable the pending first factor after device proof and reject TOTP replay."""

    if not setup.mfa_required or setup.device_confirmed_at is None:
        raise HTTPException(status.HTTP_409_CONFLICT, "MFA setup is not required")
    mfa = await session.get(AdminMfa, account.id, with_for_update=True)
    now = SystemClock().now()
    if mfa is None or mfa.pending_encrypted_secret is None:
        raise HTTPException(status.HTTP_409_CONFLICT, "MFA setup is unavailable")
    secret = decrypt_totp_secret(mfa.pending_encrypted_secret, _fernet_key(settings))
    counter = verify_totp(secret, code, now, None)
    if counter is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Authenticator code is invalid")
    recovery_codes = new_recovery_codes()
    mfa.encrypted_secret = mfa.pending_encrypted_secret
    mfa.pending_encrypted_secret = None
    mfa.pending_created_at = None
    mfa.recovery_hashes = [
        hash_token(value, settings.token_pepper.get_secret_value()) for value in recovery_codes
    ]
    mfa.enabled_at = now
    mfa.last_accepted_counter = counter
    mfa.updated_at = now
    active_sessions = await session.scalars(
        select(Session).where(Session.account_id == account.id, Session.revoked_at.is_(None))
    )
    for active in active_sessions:
        active.revoked_at = now
    setup.mfa_required = False
    return recovery_codes


def _stage_mfa(
    session: AsyncSession,
    account: Account,
    existing: AdminMfa | None,
    settings: Settings,
    now: datetime,
) -> None:
    secret = pyotp.random_base32()
    encrypted = encrypt_totp_secret(secret, _fernet_key(settings))
    if existing is None:
        session.add(
            AdminMfa(
                account_id=account.id,
                encrypted_secret=encrypted,
                pending_encrypted_secret=encrypted,
                pending_created_at=now,
                recovery_hashes=[],
                created_at=now,
                updated_at=now,
            )
        )
        return
    existing.encrypted_secret = encrypted
    existing.pending_encrypted_secret = encrypted
    existing.pending_created_at = now
    existing.updated_at = now


async def _mfa_enrollment(
    session: AsyncSession, account: Account, settings: Settings
) -> BootstrapMfaEnrollment:
    mfa = await session.get(AdminMfa, account.id, with_for_update=True)
    if mfa is None or mfa.pending_encrypted_secret is None:
        raise HTTPException(status.HTTP_409_CONFLICT, "MFA setup is unavailable")
    secret = decrypt_totp_secret(mfa.pending_encrypted_secret, _fernet_key(settings))
    uri = totp_uri(secret, account.email_normalized)
    return BootstrapMfaEnrollment(otpauth_uri=uri, qr_png_data_url=qr_png_data_url(uri))


def _fernet_key(settings: Settings) -> str:
    if settings.totp_encryption_key is None:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE, "Administrator MFA is not configured"
        )
    return settings.totp_encryption_key.get_secret_value()


def _pin_digest(pin: str, settings: Settings) -> str:
    return hash_token(f"admin-bootstrap:{pin}", settings.token_pepper.get_secret_value())


def _active_admin(account: Account | None) -> bool:
    return bool(
        account
        and account.is_admin
        and account.verified_at is not None
        and account.suspended_at is None
        and account.deleted_at is None
    )


def _event(actor_id: UUID, event_type: str, outcome: str) -> SecurityEvent:
    return SecurityEvent(
        actor_id=actor_id,
        event_type=event_type,
        outcome=outcome,
        metadata_json={},
        created_at=SystemClock().now(),
    )


def _invalid_bootstrap() -> HTTPException:
    return HTTPException(status.HTTP_401_UNAUTHORIZED, "Bootstrap credentials are invalid")
