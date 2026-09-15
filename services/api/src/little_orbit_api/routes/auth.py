"""Enumeration-resistant registration, verification, login, and recovery routes."""

from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, Header, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from .. import account_entry
from ..clock import SystemClock
from ..config import Settings, get_settings
from ..database import session_scope
from ..dependencies import current_account, request_client_ip
from ..models import Account, OneUseToken, RuntimeSetting, SecurityEvent, Session
from ..rate_limit import consume_rate_limits, request_rules
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


async def _registration_enabled(session: AsyncSession, settings: Settings) -> bool:
    control = await session.get(RuntimeSetting, "registration")
    if control is None:
        return settings.registration_open
    enabled = control.value_json.get("enabled")
    return enabled if isinstance(enabled, bool) else False


async def _rate_allowed(
    action: str,
    client_ip: str,
    subject: str,
    settings: Settings,
    *,
    ip_limit: int,
    subject_limit: int,
    minutes: int,
) -> bool:
    decision = await consume_rate_limits(
        request_rules(
            action,
            client_ip,
            subject,
            ip_limit=ip_limit,
            subject_limit=subject_limit,
            window=timedelta(minutes=minutes),
        ),
        settings=settings,
    )
    return decision.allowed


async def _record_block(session: AsyncSession, event_type: str) -> None:
    session.add(
        SecurityEvent(
            actor_id=None,
            event_type=event_type,
            outcome="blocked",
            metadata_json={},
            created_at=SystemClock().now(),
        )
    )
    await session.commit()


def _consume_reset_set(tokens: list[OneUseToken], digest: str, now: datetime) -> bool:
    """Consume the complete locked reset set only when this proof remains valid."""

    valid = any(token.token_hash == digest and token.expires_at > now for token in tokens)
    if not valid:
        return False
    for token in tokens:
        token.consumed_at = now
    return True


async def _lock_valid_reset(session: AsyncSession, digest: str, now: datetime) -> Account | None:
    account_id = await session.scalar(
        select(OneUseToken.account_id).where(
            OneUseToken.token_hash == digest,
            OneUseToken.purpose == "password_reset",
            OneUseToken.consumed_at.is_(None),
            OneUseToken.expires_at > now,
        )
    )
    if account_id is None:
        return None
    account = await session.get(Account, account_id, with_for_update=True)
    tokens = list(
        await session.scalars(
            select(OneUseToken)
            .where(
                OneUseToken.account_id == account_id,
                OneUseToken.purpose == "password_reset",
                OneUseToken.consumed_at.is_(None),
            )
            .order_by(OneUseToken.id)
            .with_for_update()
        )
    )
    if account is None or account.deleted_at is not None:
        return None
    return account if _consume_reset_set(tokens, digest, now) else None


@router.post("/register", response_model=PublicMessage, status_code=status.HTTP_202_ACCEPTED)
async def register(
    payload: RegistrationRequest,
    client_ip: str = Depends(request_client_ip),
    session: AsyncSession = Depends(session_scope),
    settings: Settings = Depends(get_settings),
) -> PublicMessage:
    """Register an adult account while keeping every public outcome neutral."""

    now = SystemClock().now()
    normalized = normalize_email(str(payload.email))
    allowed = await _rate_allowed(
        "registration",
        client_ip,
        normalized,
        settings,
        ip_limit=settings.registration_ip_per_hour,
        subject_limit=settings.registration_email_per_hour,
        minutes=60,
    )
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

    if await account_entry.create_registration(session, payload, normalized, now, settings):
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
    client_ip: str = Depends(request_client_ip),
    session: AsyncSession = Depends(session_scope),
    settings: Settings = Depends(get_settings),
) -> PublicMessage:
    """Resend at most once per five minutes while keeping account existence private."""

    now = SystemClock().now()
    normalized = normalize_email(str(payload.email))
    allowed = await _rate_allowed(
        "verification-resend",
        client_ip,
        normalized,
        settings,
        ip_limit=settings.recovery_ip_per_hour,
        subject_limit=settings.recovery_subject_per_hour,
        minutes=60,
    )
    if not allowed:
        await _record_block(session, "verification_resend_rate_limit")
        return PublicMessage(message=NEUTRAL_REGISTRATION)
    account_entry.burn_enumeration_work()
    if await account_entry.queue_verification_resend(session, normalized, now, settings):
        await session.commit()
    return PublicMessage(message=NEUTRAL_REGISTRATION)


@router.post("/login", response_model=SessionResponse)
async def login(
    payload: LoginRequest,
    client_ip: str = Depends(request_client_ip),
    session: AsyncSession = Depends(session_scope),
    settings: Settings = Depends(get_settings),
) -> SessionResponse:
    """Authenticate a verified account and issue an opaque, hashed session token."""

    normalized = normalize_email(str(payload.email))
    allowed = await _rate_allowed(
        "login",
        client_ip,
        normalized,
        settings,
        ip_limit=settings.login_ip_per_15_minutes,
        subject_limit=settings.login_subject_per_15_minutes,
        minutes=15,
    )
    if not allowed:
        await _record_block(session, "login_rate_limit")
        raise HTTPException(
            status.HTTP_429_TOO_MANY_REQUESTS,
            "Authentication is temporarily unavailable",
            headers={"Retry-After": "900"},
        )
    account = await session.scalar(
        select(Account)
        .where(Account.email_normalized == normalized)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    valid = verify_password(account.password_hash if account else _dummy_hash, payload.password)
    if (
        not valid
        or account is None
        or account.verified_at is None
        or account.suspended_at
        or account.deleted_at
    ):
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
    client_ip: str = Depends(request_client_ip),
    session: AsyncSession = Depends(session_scope),
    settings: Settings = Depends(get_settings),
) -> PublicMessage:
    """Queue a short-lived reset token while keeping account existence private."""

    normalized = normalize_email(str(payload.email))
    allowed = await _rate_allowed(
        "password-recovery",
        client_ip,
        normalized,
        settings,
        ip_limit=settings.recovery_ip_per_hour,
        subject_limit=settings.recovery_subject_per_hour,
        minutes=60,
    )
    if not allowed:
        await _record_block(session, "password_recovery_rate_limit")
        return PublicMessage(message=NEUTRAL_RECOVERY)
    account_entry.burn_enumeration_work()
    if await account_entry.queue_password_reset(session, normalized, SystemClock().now(), settings):
        await session.commit()
    return PublicMessage(message=NEUTRAL_RECOVERY)


@router.post("/reset-password", response_model=PublicMessage)
async def reset_password(
    payload: ResetPasswordRequest,
    client_ip: str = Depends(request_client_ip),
    session: AsyncSession = Depends(session_scope),
    settings: Settings = Depends(get_settings),
) -> PublicMessage:
    """Consume a reset token, replace the password, and revoke old sessions atomically."""

    allowed = await _rate_allowed(
        "password-reset",
        client_ip,
        payload.token,
        settings,
        ip_limit=settings.reset_ip_per_hour,
        subject_limit=settings.reset_subject_per_hour,
        minutes=60,
    )
    if not allowed:
        await _record_block(session, "password_reset_rate_limit")
        raise HTTPException(
            status.HTTP_429_TOO_MANY_REQUESTS,
            "Password reset is temporarily unavailable",
            headers={"Retry-After": "3600"},
        )
    now = SystemClock().now()
    digest = hash_token(payload.token, settings.token_pepper.get_secret_value())
    account = await _lock_valid_reset(session, digest, now)
    if account is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Link is invalid or expired")
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
    account = await session.get(
        Account,
        actor.id,
        with_for_update=True,
        populate_existing=True,
    )
    if account is None or account.suspended_at is not None or account.deleted_at is not None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Authentication required")
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

    account = await session.get(Account, _actor.id, with_for_update=True)
    if account is None or account.suspended_at is not None or account.deleted_at is not None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Authentication required")
    current = await session.scalar(
        select(Session)
        .where(Session.token_hash == _authorization_digest(authorization, settings))
        .with_for_update()
    )
    if current is not None and current.revoked_at is None:
        current.revoked_at = SystemClock().now()
        await session.commit()
    return PublicMessage(message="Signed out.")
