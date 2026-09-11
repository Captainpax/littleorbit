"""Owner MFA and privacy-limited console API routes."""

from datetime import timedelta
from uuid import UUID

import pyotp
from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..clock import SystemClock
from ..config import Settings, get_settings
from ..database import session_scope
from ..dependencies import current_account, current_admin
from ..models import Account, AdminMfa, SecurityEvent, Session
from ..schemas import (
    AdminConfigResponse,
    AdminEnrollmentChallenge,
    AdminEnrollmentConfirm,
    AdminEnrollmentStart,
    AdminSessionRequest,
    AdminSessionResponse,
)
from ..security import (
    decrypt_totp_secret,
    encrypt_totp_secret,
    hash_token,
    new_opaque_token,
    new_recovery_codes,
    normalize_email,
    qr_svg_data_url,
    redact_config,
    totp_uri,
    verify_password,
    verify_totp,
)

router = APIRouter(prefix="/v1/admin", tags=["administration"])


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
    expires = now + timedelta(minutes=settings.session_minutes)
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
        max_age=settings.session_minutes * 60,
        httponly=True,
        secure=settings.public_base_url.startswith("https://"),
        samesite="strict",
        path="/admin",
    )


@router.post("/mfa/start", response_model=AdminEnrollmentChallenge)
async def start_mfa(
    payload: AdminEnrollmentStart,
    actor: Account = Depends(current_account),
    session: AsyncSession = Depends(session_scope),
    settings: Settings = Depends(get_settings),
) -> AdminEnrollmentChallenge:
    """Start enrollment only after current password reauthentication."""

    if not actor.is_admin or not verify_password(actor.password_hash, payload.password):
        session.add(_event(actor.id, "admin_mfa_enrollment", "password_rejected"))
        await session.commit()
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Recent password authentication required")
    now = SystemClock().now()
    secret = pyotp.random_base32()
    encrypted = encrypt_totp_secret(secret, _fernet_key(settings))
    record = await session.get(AdminMfa, actor.id, with_for_update=True)
    if record is None:
        record = AdminMfa(
            account_id=actor.id,
            encrypted_secret=encrypted,
            recovery_hashes=[],
            created_at=now,
            updated_at=now,
        )
        session.add(record)
    else:
        record.encrypted_secret = encrypted
        record.recovery_hashes = []
        record.enabled_at = None
        record.last_accepted_counter = None
        record.updated_at = now
    uri = totp_uri(secret, actor.email_normalized)
    session.add(_event(actor.id, "admin_mfa_enrollment", "challenge_created"))
    await session.commit()
    return AdminEnrollmentChallenge(otpauth_uri=uri, qr_svg_data_url=qr_svg_data_url(uri))


@router.post("/mfa/confirm", response_model=AdminSessionResponse)
async def confirm_mfa(
    payload: AdminEnrollmentConfirm,
    http_response: Response,
    actor: Account = Depends(current_account),
    session: AsyncSession = Depends(session_scope),
    settings: Settings = Depends(get_settings),
) -> AdminSessionResponse:
    """Enable MFA after one valid code and display newly generated recovery codes once."""

    record = await session.get(AdminMfa, actor.id, with_for_update=True)
    if not actor.is_admin or record is None or record.enabled_at is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, "No pending enrollment")
    now = SystemClock().now()
    secret = decrypt_totp_secret(record.encrypted_secret, _fernet_key(settings))
    counter = verify_totp(secret, payload.code, now, None)
    if counter is None:
        session.add(_event(actor.id, "admin_mfa_enrollment", "code_rejected"))
        await session.commit()
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Authenticator code is invalid")
    recovery_codes = new_recovery_codes()
    pepper = settings.token_pepper.get_secret_value()
    record.recovery_hashes = [hash_token(code, pepper) for code in recovery_codes]
    record.enabled_at = now
    record.last_accepted_counter = counter
    record.updated_at = now
    response = await _issue_admin_session(session, actor, settings, recovery_codes)
    _set_admin_cookie(http_response, response.access_token, settings)
    session.add(_event(actor.id, "admin_mfa_enrollment", "enabled"))
    await session.commit()
    return response


@router.post("/session", response_model=AdminSessionResponse)
async def admin_session(
    payload: AdminSessionRequest,
    http_response: Response,
    session: AsyncSession = Depends(session_scope),
    settings: Settings = Depends(get_settings),
) -> AdminSessionResponse:
    """Issue an admin session after password and replay-safe TOTP or recovery proof."""

    account = await session.scalar(
        select(Account).where(Account.email_normalized == normalize_email(str(payload.email)))
    )
    password_ok = account is not None and verify_password(account.password_hash, payload.password)
    if not password_ok or account is None or not account.is_admin:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Administrator credentials are invalid")
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


def _verify_admin_proof(record: AdminMfa, payload: AdminSessionRequest, settings: Settings) -> bool:
    now = SystemClock().now()
    if payload.totp_code:
        secret = decrypt_totp_secret(record.encrypted_secret, _fernet_key(settings))
        counter = verify_totp(secret, payload.totp_code, now, record.last_accepted_counter)
        if counter is not None:
            record.last_accepted_counter = counter
            record.updated_at = now
            return True
    if payload.recovery_code:
        digest = hash_token(payload.recovery_code, settings.token_pepper.get_secret_value())
        if digest in record.recovery_hashes:
            record.recovery_hashes = [item for item in record.recovery_hashes if item != digest]
            record.updated_at = now
            return True
    return False


@router.get("/configuration", response_model=AdminConfigResponse)
async def configuration(
    _admin: Account = Depends(current_admin), settings: Settings = Depends(get_settings)
) -> AdminConfigResponse:
    """Return operational configuration with every credential field redacted."""

    visible: dict[str, object] = {
        "environment": settings.little_orbit_env,
        "public_base_url": settings.public_base_url,
        "database_url": settings.database_url,
        "session_secret": settings.session_secret.get_secret_value(),
        "token_pepper": settings.token_pepper.get_secret_value(),
        "totp_encryption_key": "configured" if settings.totp_encryption_key else "missing",
        "smtp_host": settings.smtp_host,
        "smtp_port": settings.smtp_port,
        "smtp_from": settings.smtp_from,
        "trusted_proxy_ip": settings.trusted_proxy_ip,
        "registration_open": settings.registration_open,
    }
    return AdminConfigResponse(values=redact_config(visible))
