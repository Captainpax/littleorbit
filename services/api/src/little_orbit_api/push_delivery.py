"""Reliable database-to-FCM wake delivery without placing content in push."""

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Literal
from uuid import UUID

from sqlalchemy import or_, select

from .clock import SystemClock
from .config import Settings, get_settings
from .database import SessionFactory
from .fcm import FcmClient, PushSendResult, load_credentials
from .notification_models import NotificationDelivery, NotificationDevice, NotificationEvent
from .push_tokens import clear_push_token, decrypt_push_token, invalidate_push_token

LOGGER = logging.getLogger(__name__)
RETRY_DELAY = timedelta(seconds=30)


@dataclass(frozen=True)
class ClaimedPush:
    """Opaque worker claim with no event, account, or relationship content."""

    device_id: UUID
    encrypted_token: str
    token_hash: str
    claimed_at: datetime


async def deliver_push_wakes_once(settings: Settings | None = None) -> int:
    """Wake installations with pending alerts; polling remains the fallback."""

    active_settings = settings or get_settings()
    if not _configured(active_settings):
        return 0
    now = SystemClock().now()
    claims = await _claim_pending(now)
    if not claims:
        return 0
    credentials_path = active_settings.google_application_credentials
    if credentials_path is None:
        return 0
    client = FcmClient(
        active_settings.fcm_project_id or "", load_credentials(credentials_path)
    )
    delivered = 0
    for claim in claims:
        token = decrypt_push_token(claim.encrypted_token, active_settings)
        result: PushSendResult | Literal["unreadable"] = "unreadable"
        if token is not None:
            try:
                result = await client.send_content_free(token)
            except Exception:
                LOGGER.warning("content-free FCM wake will retry")
                result = "retry"
        await _record_result(claim, result, SystemClock().now())
        delivered += result == "sent"
    return delivered


def _configured(settings: Settings) -> bool:
    path = settings.google_application_credentials
    return bool(
        settings.fcm_project_id
        and settings.push_token_encryption_key is not None
        and path is not None
        and path.is_file()
    )


async def _claim_pending(now: datetime) -> list[ClaimedPush]:
    async with SessionFactory() as session:
        pending = (
            select(NotificationDelivery.id)
            .join(NotificationEvent, NotificationEvent.id == NotificationDelivery.event_id)
            .where(
                NotificationDelivery.device_id == NotificationDevice.id,
                NotificationDelivery.displayed_at.is_(None),
                NotificationEvent.expires_at > now,
                or_(
                    NotificationDevice.push_last_success_at.is_(None),
                    NotificationEvent.created_at > NotificationDevice.push_last_success_at,
                ),
            )
            .correlate(NotificationDevice)
            .exists()
        )
        devices = list(
            await session.scalars(
                select(NotificationDevice)
                .where(
                    NotificationDevice.disabled_at.is_(None),
                    NotificationDevice.notifications_enabled.is_(True),
                    NotificationDevice.push_token_encrypted.is_not(None),
                    NotificationDevice.push_token_hash.is_not(None),
                    or_(
                        NotificationDevice.push_last_attempt_at.is_(None),
                        NotificationDevice.push_last_attempt_at <= now - RETRY_DELAY,
                    ),
                    pending,
                )
                .order_by(NotificationDevice.last_seen_at.desc())
                .limit(100)
                .with_for_update(skip_locked=True)
            )
        )
        claims = [
            ClaimedPush(
                item.id,
                item.push_token_encrypted,
                item.push_token_hash,
                now,
            )
            for item in devices
            if item.push_token_encrypted is not None and item.push_token_hash is not None
        ]
        for item in devices:
            item.push_last_attempt_at = now
        await session.commit()
        return claims


async def _record_result(
    claim: ClaimedPush,
    result: PushSendResult | Literal["unreadable"],
    now: datetime,
) -> None:
    async with SessionFactory() as session:
        device = await session.scalar(
            select(NotificationDevice)
            .where(
                NotificationDevice.id == claim.device_id,
                NotificationDevice.push_token_hash == claim.token_hash,
                NotificationDevice.push_last_attempt_at == claim.claimed_at,
            )
            .with_for_update()
        )
        if device is None:
            return
        if result == "sent":
            device.push_last_success_at = now
            device.push_failure_count = 0
        elif result == "invalid":
            invalidate_push_token(device, now)
        elif result == "unreadable":
            clear_push_token(device, now)
        else:
            device.push_failure_count = min(device.push_failure_count + 1, 1000)
        await session.commit()
