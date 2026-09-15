"""Encryption and reassignment rules for optional FCM registration tokens."""

import hashlib
import hmac
from datetime import datetime

from cryptography.fernet import Fernet, InvalidToken
from sqlalchemy import select, text, update
from sqlalchemy.ext.asyncio import AsyncSession

from .config import Settings
from .notification_models import NotificationDevice


def push_token_hash(token: str, settings: Settings) -> str:
    """Return a domain-separated lookup digest without exposing the token."""

    secret = settings.token_pepper.get_secret_value().encode()
    return hmac.new(secret, b"push-token\x00" + token.encode(), hashlib.sha256).hexdigest()


def encrypt_push_token(token: str, settings: Settings) -> str | None:
    """Encrypt a token when this installation has a dedicated key configured."""

    configured = settings.push_token_encryption_key
    if configured is None:
        return None
    return Fernet(configured.get_secret_value().encode()).encrypt(token.encode()).decode()


def decrypt_push_token(encrypted: str, settings: Settings) -> str | None:
    """Decrypt a stored token, failing closed after key rotation or corruption."""

    configured = settings.push_token_encryption_key
    if configured is None:
        return None
    try:
        return Fernet(configured.get_secret_value().encode()).decrypt(encrypted.encode()).decode()
    except (InvalidToken, UnicodeDecodeError, ValueError):
        return None


async def assign_push_token(
    session: AsyncSession,
    device: NotificationDevice,
    token: str,
    now: datetime,
    settings: Settings,
) -> bool:
    """Move one high-entropy FCM token to this authenticated installation."""

    digest = push_token_hash(token, settings)
    await session.execute(
        text("SELECT pg_advisory_xact_lock(:lock_id)"),
        {"lock_id": _digest_lock_id(digest)},
    )
    if device.push_token_hash == digest:
        if device.push_token_invalidated_at is not None:
            return False
        if (
            device.push_token_encrypted is not None
            and decrypt_push_token(device.push_token_encrypted, settings) == token
        ):
            return True
    invalidated = await session.scalar(
        select(NotificationDevice.id)
        .where(
            NotificationDevice.push_token_hash == digest,
            NotificationDevice.push_token_encrypted.is_(None),
            NotificationDevice.push_token_invalidated_at.is_not(None),
        )
        .with_for_update()
    )
    if invalidated is not None:
        return False
    encrypted = encrypt_push_token(token, settings)
    if encrypted is None:
        return False
    await session.execute(
        update(NotificationDevice)
        .where(
            NotificationDevice.push_token_hash == digest,
            NotificationDevice.id != device.id,
        )
        .values(
            push_token_encrypted=None,
            push_token_hash=None,
            push_token_refreshed_at=None,
            push_token_invalidated_at=now,
            push_last_attempt_at=None,
            push_last_success_at=None,
            push_failure_count=0,
        )
    )
    device.push_token_encrypted = encrypted
    device.push_token_hash = digest
    device.push_token_refreshed_at = now
    device.push_token_invalidated_at = None
    device.push_last_attempt_at = None
    device.push_last_success_at = None
    device.push_failure_count = 0
    return True


def _digest_lock_id(digest: str) -> int:
    """Map one token digest to PostgreSQL's signed advisory-lock namespace."""

    unsigned = int(digest[:16], 16)
    return unsigned - (1 << 64) if unsigned >= (1 << 63) else unsigned


def clear_push_token(device: NotificationDevice, now: datetime) -> None:
    """Remove push addressing while retaining the installation for safe polling."""

    device.push_token_encrypted = None
    device.push_token_hash = None
    device.push_token_refreshed_at = None
    device.push_token_invalidated_at = now
    device.push_last_attempt_at = None
    device.push_last_success_at = None
    device.push_failure_count = 0


def invalidate_push_token(device: NotificationDevice, now: datetime) -> None:
    """Remember an FCM-rejected digest so the same dead address is not restored."""

    device.push_token_encrypted = None
    device.push_token_refreshed_at = None
    device.push_token_invalidated_at = now
    device.push_last_success_at = None
    device.push_failure_count = 0
