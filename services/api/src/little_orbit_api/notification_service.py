"""Transactional rules for preferences and partner-notification delivery."""

from datetime import datetime, timedelta
from uuid import UUID

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from .clock import SystemClock
from .interaction_models import Smooch
from .models import Account, CoupleMember, Note
from .notification_models import (
    NotificationDelivery,
    NotificationDevice,
    NotificationEvent,
    NotificationPreference,
)
from .notification_schemas import NotificationEventResponse, NotificationPreferencesResponse

EVENT_TTL = timedelta(hours=24)
ACTIVE_DEVICE_WINDOW = timedelta(days=30)
NOTE_EDIT_COOLDOWN = timedelta(minutes=30)


async def preferences_for(session: AsyncSession, account_id: UUID) -> NotificationPreference:
    """Return defaults for an account that has not saved explicit choices yet."""

    preferences = await session.get(NotificationPreference, account_id)
    if preferences is not None:
        return preferences
    preferences = NotificationPreference(account_id=account_id, updated_at=SystemClock().now())
    session.add(preferences)
    await session.flush()
    return preferences


def preferences_response(item: NotificationPreference) -> NotificationPreferencesResponse:
    """Map persistence state to the versioned public contract."""

    return NotificationPreferencesResponse(
        master_enabled=item.master_enabled,
        smooches_enabled=item.smooches_enabled,
        note_editing_enabled=item.note_editing_enabled,
        daily_quiz_enabled=item.daily_quiz_enabled,
        countdowns_enabled=item.countdowns_enabled,
        weekly_summary_enabled=item.weekly_summary_enabled,
        updated_at=item.updated_at,
    )


async def enqueue_smooch_event(session: AsyncSession, smooch: Smooch) -> UUID | None:
    """Create a short-lived alert for a newly committed Smooch transaction."""

    if smooch.recipient_id is None or smooch.sender_id is None:
        return None
    preferences = await preferences_for(session, smooch.recipient_id)
    if not preferences.master_enabled or not preferences.smooches_enabled:
        return None
    event = NotificationEvent(
        recipient_id=smooch.recipient_id,
        couple_id=smooch.couple_id,
        actor_id=smooch.sender_id,
        kind="smooch_received",
        source_id=smooch.id,
        dedupe_key=f"smooch:{smooch.id}",
        created_at=smooch.sent_at,
        expires_at=smooch.sent_at + EVENT_TTL,
    )
    session.add(event)
    await session.flush()
    await create_active_deliveries(session, event)
    return smooch.recipient_id


async def enqueue_note_edit_event(
    session: AsyncSession,
    couple_id: UUID,
    actor_id: UUID,
    note_id: UUID,
    *,
    partner_viewing: bool,
) -> UUID | None:
    """Create at most one partner alert per document/editor rolling cooldown."""

    if partner_viewing:
        return None
    recipient_id = await session.scalar(
        select(CoupleMember.account_id).where(
            CoupleMember.couple_id == couple_id,
            CoupleMember.account_id != actor_id,
            CoupleMember.left_at.is_(None),
        )
    )
    if recipient_id is None:
        return None
    preferences = await preferences_for(session, recipient_id)
    if not preferences.master_enabled or not preferences.note_editing_enabled:
        return None
    now = SystemClock().now()
    recent = await session.scalar(
        select(NotificationEvent.id).where(
            NotificationEvent.recipient_id == recipient_id,
            NotificationEvent.actor_id == actor_id,
            NotificationEvent.kind == "note_editing",
            NotificationEvent.source_id == note_id,
            NotificationEvent.created_at > now - NOTE_EDIT_COOLDOWN,
        )
    )
    if recent is not None:
        return None
    event = NotificationEvent(
        recipient_id=recipient_id,
        couple_id=couple_id,
        actor_id=actor_id,
        kind="note_editing",
        source_id=note_id,
        dedupe_key=f"note-edit:{note_id}:{actor_id}:{now.isoformat()}",
        created_at=now,
        expires_at=now + EVENT_TTL,
    )
    session.add(event)
    await session.flush()
    await create_active_deliveries(session, event)
    return recipient_id


async def create_active_deliveries(session: AsyncSession, event: NotificationEvent) -> None:
    """Attach an event to every recently seen, enabled installation."""

    cutoff = SystemClock().now() - ACTIVE_DEVICE_WINDOW
    devices = list(
        await session.scalars(
            select(NotificationDevice).where(
                NotificationDevice.account_id == event.recipient_id,
                NotificationDevice.disabled_at.is_(None),
                NotificationDevice.notifications_enabled.is_(True),
                NotificationDevice.last_seen_at >= cutoff,
            )
        )
    )
    now = SystemClock().now()
    for device in devices:
        session.add(NotificationDelivery(event_id=event.id, device_id=device.id, created_at=now))


async def ensure_pending_deliveries(session: AsyncSession, device: NotificationDevice) -> None:
    """Backfill still-live events when a phone returns or first registers."""

    events = list(
        await session.scalars(
            select(NotificationEvent).where(
                NotificationEvent.recipient_id == device.account_id,
                NotificationEvent.expires_at > SystemClock().now(),
                NotificationEvent.legacy_consumed_at.is_(None),
                ~NotificationEvent.id.in_(
                    select(NotificationDelivery.event_id).where(
                        NotificationDelivery.device_id == device.id
                    )
                ),
            )
        )
    )
    now = SystemClock().now()
    for event in events:
        session.add(NotificationDelivery(event_id=event.id, device_id=device.id, created_at=now))


async def event_response(
    session: AsyncSession, event: NotificationEvent
) -> NotificationEventResponse | None:
    """Resolve current authorized display metadata without storing note titles."""

    actor_name = await session.scalar(
        select(Account.display_name).where(Account.id == event.actor_id)
    )
    if event.kind == "smooch_received":
        smooch = await session.get(Smooch, event.source_id)
        if smooch is None:
            return None
        return NotificationEventResponse(
            id=event.id,
            kind="smooch_received",
            created_at=event.created_at,
            expires_at=event.expires_at,
            actor_display_name=actor_name,
            emoji=smooch.emoji,
            phrase_key=smooch.phrase_key,
        )
    note = await session.scalar(
        select(Note).where(Note.id == event.source_id, Note.couple_id == event.couple_id)
    )
    return NotificationEventResponse(
        id=event.id,
        kind="note_editing",
        created_at=event.created_at,
        expires_at=event.expires_at,
        actor_display_name=actor_name,
        note_id=event.source_id,
        note_title=note.title if note is not None else None,
    )


async def purge_notification_state(session: AsyncSession, now: datetime) -> None:
    """Delete expired alerts and installations absent for ninety days."""

    await session.execute(
        delete(NotificationEvent).where(
            NotificationEvent.created_at <= now - timedelta(days=7)
        )
    )
    await session.execute(
        delete(NotificationDevice).where(
            NotificationDevice.last_seen_at <= now - timedelta(days=90)
        )
    )
