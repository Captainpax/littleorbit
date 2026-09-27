"""Owner MFA and privacy-limited console API routes."""

from datetime import datetime, timedelta
from typing import cast
from uuid import UUID

import pyotp
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..admin_device_models import AdminDevice, AdminDeviceSession
from ..admin_schemas import (
    AdminEnrollmentChallenge,
    AdminEnrollmentConfirm,
    AdminEnrollmentStart,
    AdminSessionResponse,
)
from ..big_orbit_auth import issue_device_session
from ..big_orbit_dependencies import (
    BigOrbitPrincipal,
    current_big_orbit_account,
    current_big_orbit_admin,
)
from ..clock import SystemClock
from ..config import Settings, get_settings
from ..database import session_scope
from ..dependencies import request_client_ip
from ..models import Account, AdminMfa, SecurityEvent, Session
from ..rate_limit import consume_rate_limits, request_rules
from ..schemas import AdminConfigResponse
from ..security import (
    decrypt_totp_secret,
    encrypt_totp_secret,
    hash_token,
    new_recovery_codes,
    qr_png_data_url,
    qr_svg_data_url,
    totp_uri,
    verify_password,
    verify_totp,
)

router = APIRouter(prefix="/v2/admin", tags=["administration"])


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
        return False
    return _verify_factor(
        record,
        payload.current_totp_code,
        payload.current_recovery_code,
        settings,
    )


async def _authorize_mfa_start(
    session: AsyncSession,
    principal: BigOrbitPrincipal,
    payload: AdminEnrollmentStart,
    settings: Settings,
) -> tuple[Account, AdminDevice, AdminMfa]:
    locked = await _lock_big_orbit_principal(session, principal)
    record = await session.get(AdminMfa, principal.account.id, with_for_update=True)
    if (
        locked is not None
        and record is not None
        and _enrollment_proof_valid(locked[0], record, payload, settings)
    ):
        return locked[0], locked[1], record
    session.add(_event(principal.account.id, "admin_mfa_enrollment", "proof_rejected"))
    await session.commit()
    raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Current administrator proof required")


def _stage_mfa_secret(record: AdminMfa, encrypted: str, now: datetime) -> None:
    """Keep the enabled factor active while staging one bounded replacement."""

    record.pending_encrypted_secret = encrypted
    record.pending_created_at = now
    record.updated_at = now


@router.post("/mfa/start", response_model=AdminEnrollmentChallenge)
async def start_mfa(
    payload: AdminEnrollmentStart,
    principal: BigOrbitPrincipal = Depends(current_big_orbit_admin),
    client_ip: str = Depends(request_client_ip),
    session: AsyncSession = Depends(session_scope),
    settings: Settings = Depends(get_settings),
) -> AdminEnrollmentChallenge:
    """Start enrollment only after current password reauthentication."""

    actor = principal.account
    allowed = await _admin_rate_allowed("admin-mfa-start", client_ip, str(actor.id), settings)
    if not allowed:
        await _reject_admin_rate_limit(session, actor.id)
    locked_actor, _device, record = await _authorize_mfa_start(
        session, principal, payload, settings
    )
    now = SystemClock().now()
    secret = pyotp.random_base32()
    encrypted = encrypt_totp_secret(secret, _fernet_key(settings))
    _stage_mfa_secret(record, encrypted, now)
    uri = totp_uri(secret, locked_actor.email_normalized)
    session.add(_event(actor.id, "admin_mfa_enrollment", "challenge_created"))
    await session.commit()
    return AdminEnrollmentChallenge(
        otpauth_uri=uri,
        qr_svg_data_url=qr_svg_data_url(uri),
        qr_png_data_url=qr_png_data_url(uri),
    )


@router.post("/mfa/confirm", response_model=AdminSessionResponse)
async def confirm_mfa(
    payload: AdminEnrollmentConfirm,
    principal: BigOrbitPrincipal = Depends(current_big_orbit_admin),
    client_ip: str = Depends(request_client_ip),
    session: AsyncSession = Depends(session_scope),
    settings: Settings = Depends(get_settings),
) -> AdminSessionResponse:
    """Enable MFA after one valid code and display newly generated recovery codes once."""

    actor = principal.account
    allowed = await _admin_rate_allowed("admin-mfa-confirm", client_ip, str(actor.id), settings)
    if not allowed:
        await _reject_admin_rate_limit(session, actor.id)
    locked = await _lock_big_orbit_principal(session, principal)
    record = await session.get(AdminMfa, actor.id, with_for_update=True)
    if locked is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Authentication required")
    locked_actor, locked_device = locked
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
    issued = await issue_device_session(session, locked_actor, locked_device, settings)
    response = AdminSessionResponse(
        access_token=issued.token,
        expires_at=issued.expires_at,
        account_id=locked_actor.id,
        recovery_codes=recovery_codes,
    )
    session.add(_event(actor.id, "admin_mfa_enrollment", "enabled"))
    await session.commit()
    return response


def _admin_account_active(account: Account | None) -> bool:
    return (
        account is not None
        and account.is_admin
        and account.verified_at is not None
        and account.suspended_at is None
        and account.deleted_at is None
    )


async def _lock_big_orbit_principal(
    session: AsyncSession,
    principal: BigOrbitPrincipal,
) -> tuple[Account, AdminDevice] | None:
    """Recheck the exact session and device after taking the account lock."""

    account = await _lock_admin_account(session, principal.account.id)
    if not _admin_account_active(account) or account is None:
        return None
    device = await session.scalar(
        select(AdminDevice)
        .where(
            AdminDevice.id == principal.device.id,
            AdminDevice.account_id == account.id,
            AdminDevice.approved_at.is_not(None),
            AdminDevice.revoked_at.is_(None),
        )
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    active_session = await session.scalar(
        select(Session)
        .join(AdminDeviceSession, AdminDeviceSession.session_id == Session.id)
        .where(
            Session.id == principal.session.id,
            Session.account_id == account.id,
            Session.revoked_at.is_(None),
            Session.expires_at > SystemClock().now(),
            Session.admin_mfa_verified.is_(True),
            AdminDeviceSession.device_id == principal.device.id,
        )
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    if active_session is None or device is None:
        return None
    return account, device


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
    _admin: Account = Depends(current_big_orbit_account),
    settings: Settings = Depends(get_settings),
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
