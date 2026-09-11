"""Enumeration-resistant registration, verification, login, and recovery routes."""

import hashlib
from datetime import timedelta
from typing import cast
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..clock import SystemClock
from ..config import Settings, get_settings
from ..database import session_scope
from ..dependencies import current_account, request_client_ip
from ..mail import enqueue_mail, recovery_body, verification_body
from ..models import Account, OneUseToken, RuntimeSetting, SecurityEvent, Session
from ..rate_limit import FixedWindowLimiter
from ..schemas import (
    ForgotPasswordRequest,
    LoginRequest,
    PublicMessage,
    RegistrationRequest,
    ResetPasswordRequest,
    SessionResponse,
    TokenRequest,
)
from ..security import hash_password, hash_token, new_opaque_token, normalize_email, verify_password

router = APIRouter(prefix="/v1/auth", tags=["authentication"])
NEUTRAL_REGISTRATION = "If registration can continue, check your email for the next step."
NEUTRAL_RECOVERY = "If that account can be recovered, an email will arrive shortly."
_dummy_hash = hash_password("timing-only-password-value")


def _limit_key(value: str, pepper: str) -> str:
    return hashlib.sha256(f"{pepper}:{value}".encode()).hexdigest()


async def _registration_enabled(session: AsyncSession, settings: Settings) -> bool:
    control = await session.get(RuntimeSetting, "registration")
    if control is None:
        return settings.registration_open
    enabled = control.value_json.get("enabled")
    return enabled if isinstance(enabled, bool) else False


async def _create_token(
    session: AsyncSession, account_id: UUID, purpose: str, minutes: int, settings: Settings
) -> str:
    raw = new_opaque_token()
    now = SystemClock().now()
    session.add(
        OneUseToken(
            account_id=account_id,
            purpose=purpose,
            token_hash=hash_token(raw, settings.token_pepper.get_secret_value()),
            expires_at=now + timedelta(minutes=minutes),
            created_at=now,
        )
    )
    return raw


@router.post("/register", response_model=PublicMessage, status_code=status.HTTP_202_ACCEPTED)
async def register(
    payload: RegistrationRequest,
    request: Request,
    client_ip: str = Depends(request_client_ip),
    session: AsyncSession = Depends(session_scope),
    settings: Settings = Depends(get_settings),
) -> PublicMessage:
    """Register an adult account while keeping every public outcome neutral."""

    now = SystemClock().now()
    normalized = normalize_email(str(payload.email))
    pepper = settings.token_pepper.get_secret_value()
    ip_limiter = cast(FixedWindowLimiter, request.app.state.registration_ip_limiter)
    email_limiter = cast(FixedWindowLimiter, request.app.state.registration_email_limiter)
    allowed = ip_limiter.allow(_limit_key(client_ip, pepper), now)
    allowed = email_limiter.allow(_limit_key(normalized, pepper), now) and allowed
    registration_enabled = await _registration_enabled(session, settings)
    blocked_event = "registration_rate_limit" if not allowed else None
    if payload.website:
        blocked_event = "registration_honeypot"
    if blocked_event is not None:
        session.add(
            SecurityEvent(
                actor_id=None,
                event_type=blocked_event,
                outcome="blocked",
                metadata_json={},
                created_at=now,
            )
        )
        await session.commit()
    if not registration_enabled or payload.website or not allowed:
        return PublicMessage(message=NEUTRAL_REGISTRATION)

    account = await session.scalar(select(Account).where(Account.email_normalized == normalized))
    if account is None:
        account = Account(
            email_normalized=normalized,
            password_hash=hash_password(payload.password),
            display_name=payload.display_name,
            is_adult=True,
            accepted_terms_version=payload.accepted_terms_version,
            created_at=now,
            updated_at=now,
        )
        session.add(account)
        await session.flush()
        raw_token = await _create_token(session, account.id, "verify_email", 24 * 60, settings)
        enqueue_mail(
            session,
            settings,
            account.email_normalized,
            "Verify your Little Orbit email",
            verification_body(settings, account.display_name, raw_token),
        )
        await session.commit()
    return PublicMessage(message=NEUTRAL_REGISTRATION)


@router.post("/verify", response_model=PublicMessage)
async def verify_email(
    payload: TokenRequest,
    session: AsyncSession = Depends(session_scope),
    settings: Settings = Depends(get_settings),
) -> PublicMessage:
    """Atomically consume a valid email verification token."""

    now = SystemClock().now()
    digest = hash_token(payload.token, settings.token_pepper.get_secret_value())
    token = await session.scalar(
        select(OneUseToken)
        .where(
            OneUseToken.token_hash == digest,
            OneUseToken.purpose == "verify_email",
            OneUseToken.consumed_at.is_(None),
            OneUseToken.expires_at > now,
        )
        .with_for_update()
    )
    if token is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Link is invalid or expired")
    account = await session.get(Account, token.account_id, with_for_update=True)
    if account is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Link is invalid or expired")
    token.consumed_at = now
    account.verified_at = now
    account.updated_at = now
    await session.commit()
    return PublicMessage(message="Email verified. You can return to Little Orbit and sign in.")


@router.post(
    "/resend-verification",
    response_model=PublicMessage,
    status_code=status.HTTP_202_ACCEPTED,
)
async def resend_verification(
    payload: ForgotPasswordRequest,
    session: AsyncSession = Depends(session_scope),
    settings: Settings = Depends(get_settings),
) -> PublicMessage:
    """Resend at most once per five minutes while keeping account existence private."""

    now = SystemClock().now()
    account = await session.scalar(
        select(Account).where(
            Account.email_normalized == normalize_email(str(payload.email)),
            Account.verified_at.is_(None),
            Account.deleted_at.is_(None),
        )
    )
    if account is None:
        return PublicMessage(message=NEUTRAL_REGISTRATION)
    outstanding = list(
        await session.scalars(
            select(OneUseToken)
            .where(
                OneUseToken.account_id == account.id,
                OneUseToken.purpose == "verify_email",
                OneUseToken.consumed_at.is_(None),
            )
            .order_by(OneUseToken.created_at.desc())
        )
    )
    if outstanding and outstanding[0].created_at > now - timedelta(minutes=5):
        return PublicMessage(message=NEUTRAL_REGISTRATION)
    for token in outstanding:
        token.consumed_at = now
    raw_token = await _create_token(session, account.id, "verify_email", 24 * 60, settings)
    enqueue_mail(
        session,
        settings,
        account.email_normalized,
        "Verify your Little Orbit email",
        verification_body(settings, account.display_name, raw_token),
    )
    await session.commit()
    return PublicMessage(message=NEUTRAL_REGISTRATION)


@router.post("/login", response_model=SessionResponse)
async def login(
    payload: LoginRequest,
    session: AsyncSession = Depends(session_scope),
    settings: Settings = Depends(get_settings),
) -> SessionResponse:
    """Authenticate a verified account and issue an opaque, hashed session token."""

    account = await session.scalar(
        select(Account).where(Account.email_normalized == normalize_email(str(payload.email)))
    )
    valid = verify_password(account.password_hash if account else _dummy_hash, payload.password)
    if not valid or account is None or account.verified_at is None or account.suspended_at:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Email or password is incorrect")
    now = SystemClock().now()
    raw = new_opaque_token()
    expires = now + timedelta(minutes=settings.session_minutes)
    session.add(
        Session(
            account_id=account.id,
            token_hash=hash_token(raw, settings.token_pepper.get_secret_value()),
            expires_at=expires,
            authenticated_at=now,
            created_at=now,
        )
    )
    await session.commit()
    return SessionResponse(access_token=raw, expires_at=expires, account_id=account.id)


@router.post("/forgot-password", response_model=PublicMessage, status_code=status.HTTP_202_ACCEPTED)
async def forgot_password(
    payload: ForgotPasswordRequest,
    session: AsyncSession = Depends(session_scope),
    settings: Settings = Depends(get_settings),
) -> PublicMessage:
    """Queue a short-lived reset token while keeping account existence private."""

    account = await session.scalar(
        select(Account).where(Account.email_normalized == normalize_email(str(payload.email)))
    )
    if account and account.deleted_at is None:
        raw_token = await _create_token(session, account.id, "password_reset", 30, settings)
        enqueue_mail(
            session,
            settings,
            account.email_normalized,
            "Reset your Little Orbit password",
            recovery_body(settings, account.display_name, raw_token),
        )
        await session.commit()
    return PublicMessage(message=NEUTRAL_RECOVERY)


@router.post("/reset-password", response_model=PublicMessage)
async def reset_password(
    payload: ResetPasswordRequest,
    session: AsyncSession = Depends(session_scope),
    settings: Settings = Depends(get_settings),
) -> PublicMessage:
    """Consume a reset token, replace the password, and revoke old sessions atomically."""

    now = SystemClock().now()
    digest = hash_token(payload.token, settings.token_pepper.get_secret_value())
    token = await session.scalar(
        select(OneUseToken)
        .where(
            OneUseToken.token_hash == digest,
            OneUseToken.purpose == "password_reset",
            OneUseToken.consumed_at.is_(None),
            OneUseToken.expires_at > now,
        )
        .with_for_update()
    )
    if token is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Link is invalid or expired")
    account = await session.get(Account, token.account_id, with_for_update=True)
    if account is None or account.deleted_at is not None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Link is invalid or expired")
    token.consumed_at = now
    account.password_hash = hash_password(payload.password)
    account.updated_at = now
    active_sessions = await session.scalars(
        select(Session).where(Session.account_id == account.id, Session.revoked_at.is_(None))
    )
    for active_session in active_sessions:
        active_session.revoked_at = now
    await session.commit()
    return PublicMessage(message="Password updated. Sign in again on your devices.")


def _authorization_digest(authorization: str | None, settings: Settings) -> str:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Authentication required")
    return hash_token(authorization[7:], settings.token_pepper.get_secret_value())


@router.post("/session/rotate", response_model=SessionResponse)
async def rotate_session(
    actor: Account = Depends(current_account),
    authorization: str | None = Header(default=None),
    session: AsyncSession = Depends(session_scope),
    settings: Settings = Depends(get_settings),
) -> SessionResponse:
    """Atomically replace the calling token so replay of the old token fails."""

    now = SystemClock().now()
    current = await session.scalar(
        select(Session)
        .where(
            Session.account_id == actor.id,
            Session.token_hash == _authorization_digest(authorization, settings),
            Session.revoked_at.is_(None),
        )
        .with_for_update()
    )
    if current is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Authentication required")
    current.revoked_at = now
    raw = new_opaque_token()
    expires = now + timedelta(minutes=settings.session_minutes)
    session.add(
        Session(
            account_id=actor.id,
            token_hash=hash_token(raw, settings.token_pepper.get_secret_value()),
            expires_at=expires,
            authenticated_at=current.authenticated_at,
            admin_mfa_verified=current.admin_mfa_verified,
            created_at=now,
        )
    )
    await session.commit()
    return SessionResponse(access_token=raw, expires_at=expires, account_id=actor.id)


@router.post("/logout", response_model=PublicMessage)
async def logout(
    _actor: Account = Depends(current_account),
    authorization: str | None = Header(default=None),
    session: AsyncSession = Depends(session_scope),
    settings: Settings = Depends(get_settings),
) -> PublicMessage:
    """Revoke the calling session idempotently."""

    current = await session.scalar(
        select(Session).where(
            Session.token_hash == _authorization_digest(authorization, settings)
        )
    )
    if current is not None and current.revoked_at is None:
        current.revoked_at = SystemClock().now()
        await session.commit()
    return PublicMessage(message="Signed out.")
