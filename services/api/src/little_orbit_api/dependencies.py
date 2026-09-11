"""FastAPI dependencies for authentication and authorization."""

from datetime import datetime

from fastapi import Depends, Header, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from .clock import SystemClock
from .config import Settings, get_settings
from .database import session_scope
from .models import Account, Session
from .security import hash_token, validated_ip_address


async def current_account(
    authorization: str | None = Header(default=None),
    session: AsyncSession = Depends(session_scope),
    settings: Settings = Depends(get_settings),
) -> Account:
    """Authenticate an opaque bearer token and return an active account."""

    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Authentication required")
    token_hash = hash_token(authorization[7:], settings.token_pepper.get_secret_value())
    now = SystemClock().now()
    statement = (
        select(Account)
        .join(Session, Session.account_id == Account.id)
        .where(
            Session.token_hash == token_hash,
            Session.revoked_at.is_(None),
            Session.expires_at > now,
            Account.suspended_at.is_(None),
            Account.deleted_at.is_(None),
        )
    )
    account = await session.scalar(statement)
    if account is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Authentication required")
    return account


async def current_admin(
    account: Account = Depends(current_account),
    authorization: str | None = Header(default=None),
    session: AsyncSession = Depends(session_scope),
    settings: Settings = Depends(get_settings),
) -> Account:
    """Require an administrator account; TOTP step-up is enforced at admin session creation."""

    token = authorization[7:] if authorization and authorization.startswith("Bearer ") else ""
    token_digest = hash_token(token, settings.token_pepper.get_secret_value())
    mfa_verified = await session.scalar(
        select(Session.admin_mfa_verified).where(
            Session.token_hash == token_digest,
            Session.revoked_at.is_(None),
            Session.expires_at > SystemClock().now(),
        )
    )
    if not account.is_admin or not mfa_verified:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Administrator access required")
    return account


def request_client_ip(request: Request, settings: Settings = Depends(get_settings)) -> str:
    """Use the address sanitized by the isolated gateway trust boundary."""

    peer = request.client.host if request.client else "unknown"
    gateway_value = request.headers.get("x-little-orbit-client-ip")
    return validated_ip_address(gateway_value) or peer


def require_recent_auth(authenticated_at: datetime, now: datetime, minutes: int = 10) -> None:
    """Require recent password authentication for sensitive enrollment actions."""

    if (now - authenticated_at).total_seconds() > minutes * 60:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Recent password authentication required")
