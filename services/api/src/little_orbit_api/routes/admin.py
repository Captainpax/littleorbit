"""Owner MFA and privacy-limited console API routes."""

from datetime import datetime, timedelta
from typing import cast
from uuid import UUID

import pyotp
from fastapi import APIRouter, Depends, Header, HTTPException, Response, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..admin_schemas import (
    AdminEnrollmentChallenge,
    AdminEnrollmentConfirm,
    AdminEnrollmentStart,
    AdminSessionRequest,
    AdminSessionResponse,
)
from ..clock import SystemClock
from ..config import Settings, get_settings
from ..database import session_scope
from ..dependencies import current_account, current_admin, request_client_ip
from ..models import Account, AdminMfa, SecurityEvent, Session
from ..rate_limit import consume_rate_limits, request_rules
from ..schemas import AdminConfigResponse
from ..security import (
    decrypt_totp_secret,
    encrypt_totp_secret,
    hash_password,
    hash_token,
    new_opaque_token,
    new_recovery_codes,
    normalize_email,
    qr_svg_data_url,
    totp_uri,
    verify_password,
    verify_totp,
)

router = APIRouter(prefix="/v1/admin", tags=["administration"])
_dummy_admin_hash = hash_password("timing-only-administrator-password")


def _fernet_key(settings: Settings) -> str:
    if settings.totp_encryption_key is None:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE, "Administrator MFA is not configured"
        )
    return settings.totp_encryption_key.get_secret_value()


def _event(actor_id: UUID, event_type: str, outcome: str) -> SecurityEvent:
    return SecurityEvent(
        actor_id=actor_id,
        event_type=event_type,
        outcome=outcome,
        metadata_json={},
        created_at=SystemClock().now(),
    )


async def _issue_admin_session(
    session: AsyncSession,
    account: Account,
    settings: Settings,
    recovery_codes: list[str] | None = None,
) -> AdminSessionResponse:
    now = SystemClock().now()
    raw = new_opaque_token()
    expires = now + timedelta(minutes=settings.admin_session_minutes)
    session.add(
        Session(
            account_id=account.id,
            token_hash=hash_token(raw, settings.token_pepper.get_secret_value()),
            expires_at=expires,
            authenticated_at=now,
            admin_mfa_verified=True,
            created_at=now,
        )
    )
    return AdminSessionResponse(
        access_token=raw,
        expires_at=expires,
        account_id=account.id,
        recovery_codes=recovery_codes or [],
    )


def _set_admin_cookie(response: Response, token: str, settings: Settings) -> None:
    """Set the browser-only console proof after MFA succeeds."""

    response.set_cookie(
        key="little_orbit_admin",
        value=token,
        max_age=settings.admin_session_minutes * 60,
        httponly=True,
        secure=settings.public_base_url.startswith("https://"),
        samesite="strict",
        path="/admin",
    )


async def _admin_rate_allowed(
    action: str, client_ip: str, subject: str, settings: Settings
) -> bool:
    decision = await consume_rate_limits(
        request_rules(
            action,
            client_ip,
            subject,
            ip_limit=settings.admin_auth_ip_per_15_minutes,
            subject_limit=settings.admin_auth_subject_per_15_minutes,
            window=timedelta(minutes=15),
        ),
        settings=settings,
    )
    return decision.allowed


async def _reject_admin_rate_limit(session: AsyncSession, actor_id: UUID | None) -> None:
    session.add(
        SecurityEvent(
            actor_id=actor_id,
            event_type="admin_auth_rate_limit",
            outcome="blocked",
            metadata_json={},
            created_at=SystemClock().now(),
        )
    )
    await session.commit()
    raise HTTPException(
        status.HTTP_429_TOO_MANY_REQUESTS,
        "Administrator authentication is temporarily unavailable",
        headers={"Retry-After": "900"},
    )


async def _lock_admin_account(session: AsyncSession, account_id: UUID) -> Account | None:
    return cast(
        Account | None,
        await session.scalar(
            select(Account)
            .where(Account.id == account_id)
            .with_for_update()
            .execution_options(populate_existing=True)
        ),
    )


def _enrollment_proof_valid(
    account: Account | None,
    record: AdminMfa | None,
    payload: AdminEnrollmentStart,
    settings: Settings,
) -> bool:
    if (
        account is None
        or not account.is_admin
        or account.verified_at is None
        or account.suspended_at is not None
        or account.deleted_at is not None
    ):
        return False
    if not verify_password(account.password_hash, payload.password):
        return False
    if record is None or record.enabled_at is None:
        return True
    return _verify_factor(
        record,
        payload.current_totp_code,
        payload.current_recovery_code,
        settings,
    )


async def _authorize_mfa_start(
    session: AsyncSession,
    actor: Account,
    payload: AdminEnrollmentStart,
    authorization: str | None,
    settings: Settings,
) -> AdminMfa | None:
    locked_actor = await _lock_admin_account(session, actor.id)
    record = await session.get(AdminMfa, actor.id, with_for_update=True)
    session_is_live = await _request_session_active(session, actor.id, authorization, settings)
    if session_is_live and _enrollment_proof_valid(locked_actor, record, payload, settings):
        return record
    session.add(_event(actor.id, "admin_mfa_enrollment", "proof_rejected"))
    await session.commit()
    raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Current administrator proof required")


def _stage_mfa_secret(
    record: AdminMfa | None, account_id: UUID, encrypted: str, now: datetime
) -> AdminMfa:
    if record is None:
        return AdminMfa(
            account_id=account_id,
            encrypted_secret=encrypted,
            pending_encrypted_secret=encrypted,
            pending_created_at=now,
            recovery_hashes=[],
            created_at=now,
            updated_at=now,
        )
    if record.enabled_at is None:
        record.encrypted_secret = encrypted
    record.pending_encrypted_secret = encrypted
    record.pending_created_at = now
    record.updated_at = now
    return record


@router.post("/mfa/start", response_model=AdminEnrollmentChallenge)
async def start_mfa(
    payload: AdminEnrollmentStart,
    actor: Account = Depends(current_account),
    authorization: str | None = Header(default=None),
    client_ip: str = Depends(request_client_ip),
    session: AsyncSession = Depends(session_scope),
    settings: Settings = Depends(get_settings),
) -> AdminEnrollmentChallenge:
    """Start enrollment only after current password reauthentication."""

    allowed = await _admin_rate_allowed("admin-mfa-start", client_ip, str(actor.id), settings)
    if not allowed:
        await _reject_admin_rate_limit(session, actor.id)
    record = await _authorize_mfa_start(session, actor, payload, authorization, settings)
    now = SystemClock().now()
    secret = pyotp.random_base32()
    encrypted = encrypt_totp_secret(secret, _fernet_key(settings))
    staged = _stage_mfa_secret(record, actor.id, encrypted, now)
    if record is None:
        session.add(staged)
    uri = totp_uri(secret, actor.email_normalized)
    session.add(_event(actor.id, "admin_mfa_enrollment", "challenge_created"))
    await session.commit()
    return AdminEnrollmentChallenge(otpauth_uri=uri, qr_svg_data_url=qr_svg_data_url(uri))


@router.post("/mfa/confirm", response_model=AdminSessionResponse)
async def confirm_mfa(
    payload: AdminEnrollmentConfirm,
    http_response: Response,
    actor: Account = Depends(current_account),
    authorization: str | None = Header(default=None),
    client_ip: str = Depends(request_client_ip),
    session: AsyncSession = Depends(session_scope),
    settings: Settings = Depends(get_settings),
) -> AdminSessionResponse:
    """Enable MFA after one valid code and display newly generated recovery codes once."""

    allowed = await _admin_rate_allowed("admin-mfa-confirm", client_ip, str(actor.id), settings)
    if not allowed:
        await _reject_admin_rate_limit(session, actor.id)
    locked_actor = await _lock_admin_account(session, actor.id)
    record = await session.get(AdminMfa, actor.id, with_for_update=True)
    active = _admin_account_active(locked_actor) and await _request_session_active(
        session, actor.id, authorization, settings
    )
    if not active or locked_actor is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Authentication required")
    if record is None:
        raise HTTPException(status.HTTP_409_CONFLICT, "No pending enrollment")
    now = SystemClock().now()
    pending_secret = _pending_secret(record, now, settings)
    if pending_secret is None:
        record.pending_encrypted_secret = None
        record.pending_created_at = None
        await session.commit()
        raise HTTPException(status.HTTP_409_CONFLICT, "No pending enrollment")
    secret = decrypt_totp_secret(pending_secret, _fernet_key(settings))
    counter = verify_totp(secret, payload.code, now, None)
    if counter is None:
        session.add(_event(actor.id, "admin_mfa_enrollment", "code_rejected"))
        await session.commit()
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Authenticator code is invalid")
    recovery_codes = new_recovery_codes()
    pepper = settings.token_pepper.get_secret_value()
    record.encrypted_secret = pending_secret
    record.pending_encrypted_secret = None
    record.pending_created_at = None
    record.recovery_hashes = [hash_token(code, pepper) for code in recovery_codes]
    record.enabled_at = now
    record.last_accepted_counter = counter
    record.updated_at = now
    await _revoke_sessions(session, actor.id, now)
    response = await _issue_admin_session(session, locked_actor, settings, recovery_codes)
    _set_admin_cookie(http_response, response.access_token, settings)
    session.add(_event(actor.id, "admin_mfa_enrollment", "enabled"))
    await session.commit()
    return response


@router.post("/session", response_model=AdminSessionResponse)
async def admin_session(
    payload: AdminSessionRequest,
    http_response: Response,
    client_ip: str = Depends(request_client_ip),
    session: AsyncSession = Depends(session_scope),
    settings: Settings = Depends(get_settings),
) -> AdminSessionResponse:
    """Issue an admin session after password and replay-safe TOTP or recovery proof."""

    normalized = normalize_email(str(payload.email))
    allowed = await _admin_rate_allowed("admin-session", client_ip, normalized, settings)
    if not allowed:
        await _reject_admin_rate_limit(session, None)
    account = await _admin_login_account(session, normalized, payload.password)
    record = await session.get(AdminMfa, account.id, with_for_update=True)
    if record is None or record.enabled_at is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Administrator MFA is required")
    accepted = _verify_admin_proof(record, payload, settings)
    session.add(_event(account.id, "admin_session", "accepted" if accepted else "rejected"))
    if not accepted:
        await session.commit()
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Administrator credentials are invalid")
    response = await _issue_admin_session(session, account, settings)
    _set_admin_cookie(http_response, response.access_token, settings)
    await session.commit()
    return response


async def _admin_login_account(
    session: AsyncSession, normalized_email: str, password: str
) -> Account:
    account = await session.scalar(
        select(Account)
        .where(Account.email_normalized == normalized_email)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    password_ok = verify_password(
        account.password_hash if account is not None else _dummy_admin_hash,
        password,
    )
    if not password_ok or not _admin_account_active(account) or account is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Administrator credentials are invalid")
    return account


def _admin_account_active(account: Account | None) -> bool:
    return (
        account is not None
        and account.is_admin
        and account.verified_at is not None
        and account.suspended_at is None
        and account.deleted_at is None
    )


async def _request_session_active(
    session: AsyncSession,
    account_id: UUID,
    authorization: str | None,
    settings: Settings,
) -> bool:
    if not authorization or not authorization.startswith("Bearer "):
        return False
    digest = hash_token(authorization[7:], settings.token_pepper.get_secret_value())
    return (
        await session.scalar(
            select(Session.id).where(
                Session.account_id == account_id,
                Session.token_hash == digest,
                Session.revoked_at.is_(None),
                Session.expires_at > SystemClock().now(),
            )
        )
        is not None
    )


def _verify_admin_proof(record: AdminMfa, payload: AdminSessionRequest, settings: Settings) -> bool:
    return _verify_factor(record, payload.totp_code, payload.recovery_code, settings)


def _verify_factor(
    record: AdminMfa,
    totp_code: str | None,
    recovery_code: str | None,
    settings: Settings,
) -> bool:
    now = SystemClock().now()
    if totp_code:
        secret = decrypt_totp_secret(record.encrypted_secret, _fernet_key(settings))
        counter = verify_totp(secret, totp_code, now, record.last_accepted_counter)
        if counter is not None:
            record.last_accepted_counter = counter
            record.updated_at = now
            return True
    if recovery_code:
        digest = hash_token(recovery_code, settings.token_pepper.get_secret_value())
        if digest in record.recovery_hashes:
            record.recovery_hashes = [item for item in record.recovery_hashes if item != digest]
            record.updated_at = now
            return True
    return False


def _pending_secret(record: AdminMfa, now: datetime, settings: Settings) -> str | None:
    cutoff = now - timedelta(minutes=settings.admin_mfa_enrollment_minutes)
    created_at = record.pending_created_at or record.updated_at
    if created_at < cutoff:
        return None
    if record.pending_encrypted_secret is not None:
        return record.pending_encrypted_secret
    return record.encrypted_secret if record.enabled_at is None else None


async def _revoke_sessions(session: AsyncSession, account_id: UUID, now: datetime) -> None:
    active_sessions = await session.scalars(
        select(Session).where(Session.account_id == account_id, Session.revoked_at.is_(None))
    )
    for active_session in active_sessions:
        active_session.revoked_at = now


@router.get("/configuration", response_model=AdminConfigResponse)
async def configuration(
    _admin: Account = Depends(current_admin), settings: Settings = Depends(get_settings)
) -> AdminConfigResponse:
    """Return only explicitly approved operational configuration fields."""

    visible: dict[str, object] = {
        "environment": settings.little_orbit_env,
        "public_base_url": settings.public_base_url,
        "database": "configured",
        "totp_encryption": "configured" if settings.totp_encryption_key else "missing",
        "outbox_encryption": "configured" if settings.outbox_encryption_key else "missing",
        "smtp_host": settings.smtp_host,
        "smtp_port": settings.smtp_port,
        "smtp_from": settings.smtp_from,
        "smtp_starttls": settings.smtp_starttls,
        "smtp_auth": "configured" if settings.smtp_username else "missing",
        "trusted_proxy_ip": settings.trusted_proxy_ip,
        "registration_open": settings.registration_open,
        "app_session_minutes": settings.session_minutes,
        "admin_session_minutes": settings.admin_session_minutes,
    }
    return AdminConfigResponse(values=visible)
