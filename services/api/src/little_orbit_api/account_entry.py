"""Atomic account registration and recovery-email issuance."""

from datetime import datetime, timedelta
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from .clock import SystemClock
from .config import Settings
from .mail import enqueue_mail, recovery_body, verification_body
from .models import Account, OneUseToken
from .schemas import RegistrationRequest
from .security import hash_password, hash_token, new_opaque_token, verify_password

_TIMING_PASSWORD = "timing-only-password-value"
_TIMING_PASSWORD_HASH = hash_password(_TIMING_PASSWORD)
_RECOVERY_COOLDOWN = timedelta(minutes=5)


def burn_enumeration_work() -> None:
    """Apply the same dominant password work before an email-address branch."""

    verify_password(_TIMING_PASSWORD_HASH, _TIMING_PASSWORD)


async def create_registration(
    session: AsyncSession,
    payload: RegistrationRequest,
    normalized_email: str,
    now: datetime,
    settings: Settings,
) -> bool:
    """Atomically create one pending account and its first verification email."""

    created_id = await session.scalar(
        insert(Account)
        .values(
            id=uuid4(),
            email_normalized=normalized_email,
            password_hash=hash_password(payload.password),
            display_name=payload.display_name,
            is_adult=True,
            accepted_terms_version=payload.accepted_terms_version,
            is_admin=False,
            created_at=now,
            updated_at=now,
        )
        .on_conflict_do_nothing(index_elements=[Account.email_normalized])
        .returning(Account.id)
    )
    if created_id is None:
        return False
    raw_token = await _create_token(session, created_id, "verify_email", 24 * 60, settings)
    enqueue_mail(
        session,
        settings,
        normalized_email,
        "Verify your Little Orbit email",
        verification_body(settings, payload.display_name, raw_token),
    )
    return True


async def queue_verification_resend(
    session: AsyncSession,
    normalized_email: str,
    now: datetime,
    settings: Settings,
) -> bool:
    """Serialize the verification cooldown and queue at most one current link."""

    account = await session.scalar(
        select(Account)
        .where(
            Account.email_normalized == normalized_email,
            Account.verified_at.is_(None),
            Account.deleted_at.is_(None),
        )
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    if account is None:
        return False
    outstanding = await _lock_tokens(session, account.id, "verify_email")
    if _inside_cooldown(outstanding, now):
        return False
    _consume_tokens(outstanding, now)
    raw_token = await _create_token(session, account.id, "verify_email", 24 * 60, settings)
    enqueue_mail(
        session,
        settings,
        account.email_normalized,
        "Verify your Little Orbit email",
        verification_body(settings, account.display_name, raw_token),
    )
    return True


async def queue_password_reset(
    session: AsyncSession,
    normalized_email: str,
    now: datetime,
    settings: Settings,
) -> bool:
    """Serialize recovery issuance and queue one link after the cooldown."""

    account = await session.scalar(
        select(Account)
        .where(Account.email_normalized == normalized_email)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    if account is None or account.deleted_at is not None:
        return False
    outstanding = await _lock_tokens(session, account.id, "password_reset")
    if _inside_cooldown(outstanding, now):
        return False
    _consume_tokens(outstanding, now)
    raw_token = await _create_token(session, account.id, "password_reset", 30, settings)
    enqueue_mail(
        session,
        settings,
        account.email_normalized,
        "Reset your Little Orbit password",
        recovery_body(settings, account.display_name, raw_token),
    )
    return True


async def _create_token(
    session: AsyncSession,
    account_id: UUID,
    purpose: str,
    minutes: int,
    settings: Settings,
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


async def _lock_tokens(session: AsyncSession, account_id: UUID, purpose: str) -> list[OneUseToken]:
    return list(
        await session.scalars(
            select(OneUseToken)
            .where(
                OneUseToken.account_id == account_id,
                OneUseToken.purpose == purpose,
                OneUseToken.consumed_at.is_(None),
            )
            .order_by(OneUseToken.created_at.desc(), OneUseToken.id)
            .with_for_update()
        )
    )


def _inside_cooldown(tokens: list[OneUseToken], now: datetime) -> bool:
    return bool(tokens and tokens[0].created_at > now - _RECOVERY_COOLDOWN)


def _consume_tokens(tokens: list[OneUseToken], now: datetime) -> None:
    for token in tokens:
        token.consumed_at = now
