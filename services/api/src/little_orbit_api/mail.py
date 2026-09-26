"""Encrypted transactional outbox and provider-neutral SMTP delivery."""

import asyncio
import smtplib
from datetime import timedelta
from email.message import EmailMessage

from cryptography.fernet import Fernet
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from .clock import SystemClock
from .config import Settings
from .database import SessionFactory
from .models import MailOutbox


def _outbox_key(settings: Settings) -> bytes:
    if settings.outbox_encryption_key is None:
        raise RuntimeError("OUTBOX_ENCRYPTION_KEY must be configured")
    return settings.outbox_encryption_key.get_secret_value().encode()


def enqueue_mail(
    session: AsyncSession, settings: Settings, recipient: str, subject: str, body: str
) -> None:
    """Encrypt an email body and add it to the caller's database transaction."""

    now = SystemClock().now()
    ciphertext = Fernet(_outbox_key(settings)).encrypt(body.encode()).decode()
    session.add(
        MailOutbox(
            recipient=recipient,
            subject=subject,
            encrypted_body=ciphertext,
            attempts=0,
            next_attempt_at=now,
            created_at=now,
        )
    )


def verification_body(settings: Settings, display_name: str, token: str) -> str:
    """Create a plain-text email verification message."""

    link = f"{settings.public_base_url}/verify-email#token={token}"
    return f"Hello {display_name},\n\nVerify your Little Orbit email within 24 hours:\n{link}\n"


def recovery_body(settings: Settings, display_name: str, token: str) -> str:
    """Create a plain-text password recovery message."""

    link = f"{settings.public_base_url}/reset-password#token={token}"
    return f"Hello {display_name},\n\nReset your Little Orbit password within 30 minutes:\n{link}\n"


def _send_smtp(settings: Settings, row: MailOutbox, body: str) -> None:
    message = EmailMessage()
    message["From"] = settings.smtp_from
    message["To"] = row.recipient
    message["Subject"] = row.subject
    message.set_content(body)
    with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=20) as smtp:
        if settings.smtp_starttls:
            smtp.starttls()
        if settings.smtp_username and settings.smtp_password:
            smtp.login(settings.smtp_username, settings.smtp_password.get_secret_value())
        smtp.send_message(message)


async def deliver_pending_mail(settings: Settings, limit: int = 20) -> None:
    """Deliver a bounded batch, retaining encrypted payloads for retry."""

    now = SystemClock().now()
    async with SessionFactory() as session:
        rows = list(
            await session.scalars(
                select(MailOutbox)
                .where(MailOutbox.delivered_at.is_(None), MailOutbox.next_attempt_at <= now)
                .order_by(MailOutbox.created_at)
                .limit(limit)
                .with_for_update(skip_locked=True)
            )
        )
        for row in rows:
            try:
                body = Fernet(_outbox_key(settings)).decrypt(row.encrypted_body.encode()).decode()
                await asyncio.to_thread(_send_smtp, settings, row, body)
                row.delivered_at = SystemClock().now()
                row.encrypted_body = ""
            except (OSError, smtplib.SMTPException):
                row.attempts += 1
                delay_minutes = min(60, 2 ** min(row.attempts, 6))
                row.next_attempt_at = SystemClock().now() + timedelta(minutes=delay_minutes)
        await session.commit()
