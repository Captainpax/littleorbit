"""Reusable live-session checks for long-running authenticated WebSockets."""

from dataclasses import dataclass
from typing import cast
from uuid import UUID

from sqlalchemy import select

from .clock import SystemClock
from .config import get_settings
from .database import SessionFactory
from .models import Account, Session
from .security import hash_token


@dataclass(frozen=True)
class SocketIdentity:
    """Privacy-minimized WebSocket identity retaining only the session digest."""

    account_id: UUID
    token_hash: str


async def authenticate_socket(authorization: str) -> SocketIdentity | None:
    """Authenticate a bearer header against an active account and session."""

    if not authorization.startswith("Bearer ") or len(authorization) <= 7:
        return None
    settings = get_settings()
    digest = hash_token(authorization[7:], settings.token_pepper.get_secret_value())
    account_id = await _active_account_id(digest)
    return SocketIdentity(account_id, digest) if account_id is not None else None


async def socket_session_active(identity: SocketIdentity) -> bool:
    """Revalidate a socket after connection so revocation has a bounded delay."""

    return await _active_account_id(identity.token_hash, identity.account_id) is not None


async def _active_account_id(
    token_hash: str, expected_account_id: UUID | None = None
) -> UUID | None:
    async with SessionFactory() as session:
        statement = (
            select(Session.account_id)
            .join(Account, Account.id == Session.account_id)
            .where(
                Session.token_hash == token_hash,
                Session.revoked_at.is_(None),
                Session.expires_at > SystemClock().now(),
                Account.suspended_at.is_(None),
                Account.deleted_at.is_(None),
            )
        )
        if expected_account_id is not None:
            statement = statement.where(Session.account_id == expected_account_id)
        return cast(UUID | None, await session.scalar(statement))
