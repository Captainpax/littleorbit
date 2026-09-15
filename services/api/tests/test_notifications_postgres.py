"""PostgreSQL integration tests for installation-scoped partner alerts."""

import asyncio
import os
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import httpx
import pytest
import pytest_asyncio
from sqlalchemy import func, inspect, select, text

pytestmark = [
    pytest.mark.skipif(
        not os.getenv("LITTLE_ORBIT_TEST_DATABASE_URL"),
        reason="set LITTLE_ORBIT_TEST_DATABASE_URL to an isolated PostgreSQL database",
    ),
    pytest.mark.asyncio(loop_scope="session"),
]

from little_orbit_api.config import get_settings  # noqa: E402
from little_orbit_api.database import Base, SessionFactory, engine  # noqa: E402
from little_orbit_api.interaction_models import Smooch  # noqa: E402
from little_orbit_api.main import create_app  # noqa: E402
from little_orbit_api.models import Account, Couple, CoupleMember, Session  # noqa: E402
from little_orbit_api.notification_models import (  # noqa: E402
    NotificationDelivery,
    NotificationDevice,
    NotificationEvent,
    NotificationPreference,
)
from little_orbit_api.notification_service import (  # noqa: E402
    discard_disabled_events,
    enqueue_note_edit_event,
    ensure_pending_deliveries,
    preferences_for,
)
from little_orbit_api.relationship_service import end_active_relationship  # noqa: E402
from little_orbit_api.security import hash_token  # noqa: E402


@pytest_asyncio.fixture(autouse=True, loop_scope="session")
async def clean_database() -> None:
    """Keep destructive notification checks inside the named isolated database."""

    async with engine.begin() as connection:
        existing = set(await connection.run_sync(lambda sync: inspect(sync).get_table_names()))
        quote = connection.dialect.identifier_preparer.quote
        tables = ", ".join(
            quote(table.name) for table in Base.metadata.sorted_tables if table.name in existing
        )
        await connection.execute(text(f"TRUNCATE TABLE {tables} RESTART IDENTITY CASCADE"))


def _account(email: str) -> Account:
    now = datetime.now(UTC)
    return Account(
        id=uuid4(),
        email_normalized=email,
        password_hash="unused-in-notification-tests",
        display_name=email.split("@", 1)[0],
        is_adult=True,
        accepted_terms_version="2026-09-10",
        verified_at=now,
        is_admin=False,
        created_at=now,
        updated_at=now,
    )


def _device(account_id: UUID) -> NotificationDevice:
    now = datetime.now(UTC)
    return NotificationDevice(
        id=uuid4(),
        account_id=account_id,
        device_id=uuid4(),
        platform="android",
        app_version_code=140,
        notifications_enabled=True,
        last_seen_at=now,
    )


async def _seed_pair() -> tuple[Account, Account, Couple]:
    first = _account("first@example.com")
    second = _account("second@example.com")
    now = datetime.now(UTC)
    couple = Couple(
        id=uuid4(),
        proximity_threshold_m=100,
        proximity_algorithm_version=2,
        home_timezone="America/Los_Angeles",
        created_at=now,
        updated_at=now,
    )
    async with SessionFactory() as session:
        session.add_all([first, second, couple])
        session.add_all(
            [
                CoupleMember(
                    couple_id=couple.id,
                    account_id=account.id,
                    joined_at=now,
                    intimacy_enabled=False,
                    location_enabled=False,
                )
                for account in (first, second)
            ]
        )
        await session.commit()
    return first, second, couple


async def _authorize(account_id: UUID, raw_token: str) -> None:
    now = datetime.now(UTC)
    async with SessionFactory() as session:
        session.add(
            Session(
                account_id=account_id,
                token_hash=hash_token(
                    raw_token, get_settings().token_pepper.get_secret_value()
                ),
                expires_at=now + timedelta(hours=1),
                authenticated_at=now,
                admin_mfa_verified=False,
                created_at=now,
            )
        )
        await session.commit()


async def _smooch_event(
    sender: Account, recipient: Account, couple: Couple, device: NotificationDevice
) -> tuple[Smooch, NotificationEvent]:
    now = datetime.now(UTC)
    smooch = Smooch(
        id=uuid4(),
        operation_id=uuid4(),
        couple_id=couple.id,
        sender_id=sender.id,
        recipient_id=recipient.id,
        emoji="💜",
        phrase_key="thinking",
        sent_at=now,
    )
    event = NotificationEvent(
        id=uuid4(),
        recipient_id=recipient.id,
        couple_id=couple.id,
        actor_id=sender.id,
        kind="smooch_received",
        source_id=smooch.id,
        dedupe_key=f"smooch:{smooch.id}",
        created_at=now,
        expires_at=now + timedelta(hours=24),
    )
    async with SessionFactory() as session:
        session.add_all([device, smooch, event])
        await session.flush()
        session.add(
            NotificationDelivery(event_id=event.id, device_id=device.id, created_at=now)
        )
        await session.commit()
    return smooch, event


async def test_legacy_ack_cannot_consume_modern_installation_delivery() -> None:
    """An in-flight RC11 worker must not hide a Smooch from RC12+ devices."""

    sender, recipient, couple = await _seed_pair()
    bearer = "notification-session-token-with-enough-entropy"
    await _authorize(recipient.id, bearer)
    first_device = _device(recipient.id)
    second_device = _device(recipient.id)
    smooch, event = await _smooch_event(sender, recipient, couple, first_device)
    async with SessionFactory() as session:
        session.add(second_device)
        await session.commit()

    headers = {"Authorization": f"Bearer {bearer}"}
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=create_app()), base_url="http://localhost"
    ) as client:
        legacy = await client.post(
            "/v1/smooches/deliveries/ack",
            headers=headers,
            json={"smooch_ids": [str(smooch.id)]},
        )
        pending = await client.get(
            "/v1/notifications/pending",
            headers=headers,
            params={"device_id": str(second_device.device_id)},
        )

    assert legacy.status_code == 204
    assert pending.status_code == 200
    assert [item["id"] for item in pending.json()] == [str(event.id)]


async def test_acknowledgement_is_independent_for_each_installation() -> None:
    """Displaying an event on one phone cannot acknowledge a second phone."""

    sender, recipient, couple = await _seed_pair()
    bearer = "second-notification-session-with-enough-entropy"
    await _authorize(recipient.id, bearer)
    first = _device(recipient.id)
    second = _device(recipient.id)
    _, event = await _smooch_event(sender, recipient, couple, first)
    async with SessionFactory() as session:
        session.add(second)
        await session.flush()
        await ensure_pending_deliveries(session, second)
        await session.commit()

    headers = {"Authorization": f"Bearer {bearer}"}
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=create_app()), base_url="http://localhost"
    ) as client:
        acknowledged = await client.post(
            "/v1/notifications/deliveries/ack",
            headers=headers,
            json={"device_id": str(first.device_id), "event_ids": [str(event.id)]},
        )
        first_pending = await client.get(
            "/v1/notifications/pending",
            headers=headers,
            params={"device_id": str(first.device_id)},
        )
        second_pending = await client.get(
            "/v1/notifications/pending",
            headers=headers,
            params={"device_id": str(second.device_id)},
        )

    assert acknowledged.status_code == 204
    assert first_pending.json() == []
    assert [item["id"] for item in second_pending.json()] == [str(event.id)]


async def test_ack_rejects_another_accounts_installation_before_event_lookup() -> None:
    """A valid couple member cannot use a partner device to probe or consume an event."""

    sender, recipient, couple = await _seed_pair()
    bearer = "sender-notification-session-with-enough-entropy"
    await _authorize(sender.id, bearer)
    recipient_device = _device(recipient.id)
    _, event = await _smooch_event(sender, recipient, couple, recipient_device)

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=create_app()), base_url="http://localhost"
    ) as client:
        response = await client.post(
            "/v1/notifications/deliveries/ack",
            headers={"Authorization": f"Bearer {bearer}"},
            json={
                "device_id": str(recipient_device.device_id),
                "event_ids": [str(event.id)],
            },
        )

    assert response.status_code == 404
    async with SessionFactory() as session:
        displayed = await session.scalar(
            select(NotificationDelivery.displayed_at).where(
                NotificationDelivery.event_id == event.id
            )
        )
    assert displayed is None


async def test_concurrent_backfill_is_retry_safe() -> None:
    """Concurrent device heartbeats cannot fail on duplicate delivery creation."""

    sender, recipient, couple = await _seed_pair()
    device = _device(recipient.id)
    _, event = await _smooch_event(sender, recipient, couple, device)
    async with SessionFactory() as session:
        await session.execute(
            text("DELETE FROM notification_deliveries WHERE event_id = :event_id"),
            {"event_id": event.id},
        )
        await session.commit()

    async def backfill() -> None:
        async with SessionFactory() as session:
            current = await session.get(NotificationDevice, device.id)
            assert current is not None
            await ensure_pending_deliveries(session, current)
            await session.commit()

    await asyncio.gather(backfill(), backfill())
    async with SessionFactory() as session:
        count = await session.scalar(
            select(func.count())
            .select_from(NotificationDelivery)
            .where(NotificationDelivery.event_id == event.id)
        )
    assert count == 1


async def test_concurrent_default_preferences_create_one_locked_row() -> None:
    """First-run polling and Settings may initialize choices at the same time."""

    account = _account("preference-race@example.com")
    async with SessionFactory() as session:
        session.add(account)
        await session.commit()

    async def initialize() -> None:
        async with SessionFactory() as session:
            result = await preferences_for(session, account.id)
            assert result.master_enabled
            await session.commit()

    await asyncio.gather(initialize(), initialize())
    async with SessionFactory() as session:
        count = await session.scalar(
            select(func.count()).select_from(NotificationPreference)
        )
    assert count == 1


async def test_disabled_category_discards_waiting_events() -> None:
    """Re-enabling alerts must not replay events received while a category was off."""

    sender, recipient, couple = await _seed_pair()
    device = _device(recipient.id)
    await _smooch_event(sender, recipient, couple, device)
    preferences = NotificationPreference(
        account_id=recipient.id,
        master_enabled=True,
        smooches_enabled=False,
        note_editing_enabled=True,
        daily_quiz_enabled=True,
        countdowns_enabled=True,
        together_time_enabled=True,
        weekly_summary_enabled=True,
        updated_at=datetime.now(UTC),
    )
    async with SessionFactory() as session:
        session.add(preferences)
        await session.flush()
        await discard_disabled_events(session, preferences)
        await session.commit()
        assert await session.scalar(select(func.count()).select_from(NotificationEvent)) == 0


async def test_note_edit_cooldown_and_active_view_suppression() -> None:
    """Document alerts coalesce for 30 minutes and skip an actively viewing partner."""

    first, second, couple = await _seed_pair()
    note_id = uuid4()
    async with SessionFactory() as session:
        initial = await enqueue_note_edit_event(
            session, couple.id, first.id, note_id, partner_viewing=False
        )
        duplicate = await enqueue_note_edit_event(
            session, couple.id, first.id, note_id, partner_viewing=False
        )
        suppressed = await enqueue_note_edit_event(
            session, couple.id, second.id, note_id, partner_viewing=True
        )
        await session.commit()
        count = await session.scalar(select(func.count()).select_from(NotificationEvent))

    assert initial == second.id
    assert duplicate is None
    assert suppressed is None
    assert count == 1


async def test_unpair_purges_events_deliveries_and_disables_installation() -> None:
    """Ending a relationship immediately removes every relationship alert path."""

    sender, recipient, couple = await _seed_pair()
    device = _device(recipient.id)
    await _smooch_event(sender, recipient, couple, device)
    ended_at = datetime.now(UTC)
    async with SessionFactory() as session:
        assert await end_active_relationship(session, sender.id, ended_at) == couple.id
        await session.commit()

    async with SessionFactory() as session:
        current = await session.get(NotificationDevice, device.id)
        assert current is not None
        assert current.disabled_at == ended_at
        assert not current.notifications_enabled
        assert await session.scalar(select(func.count()).select_from(NotificationEvent)) == 0
        assert await session.scalar(select(func.count()).select_from(NotificationDelivery)) == 0


async def test_ended_relationship_routes_return_the_android_purge_contract() -> None:
    """Every active-couple race returns the same structured client purge signal."""

    _, recipient, couple = await _seed_pair()
    bearer = "ended-relationship-session-with-enough-entropy"
    await _authorize(recipient.id, bearer)
    async with SessionFactory() as session:
        current = await session.get(Couple, couple.id, with_for_update=True)
        assert current is not None
        current.ended_at = datetime.now(UTC)
        await session.commit()

    routes = (
        "/v1/couple/preferences",
        "/v1/smooches/status",
        "/v1/together-time",
        "/v2/together-time",
        "/v3/together-time",
        f"/v1/notifications/pending?device_id={uuid4()}",
    )
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=create_app()), base_url="http://localhost"
    ) as client:
        for path in routes:
            response = await client.get(
                path, headers={"Authorization": f"Bearer {bearer}"}
            )
            assert response.status_code == 409, path
            assert response.json()["detail"]["code"] == "relationship_inactive", path


async def test_repeated_unpair_returns_the_android_purge_contract() -> None:
    """An unpair retry cannot strand local relationship data behind a generic error."""

    actor, _, _ = await _seed_pair()
    bearer = "repeated-unpair-session-with-enough-entropy"
    await _authorize(actor.id, bearer)
    headers = {"Authorization": f"Bearer {bearer}"}
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=create_app()), base_url="http://localhost"
    ) as client:
        first = await client.post("/v1/couple/unpair", headers=headers)
        repeated = await client.post("/v1/couple/unpair", headers=headers)

    assert first.status_code == 200
    assert repeated.status_code == 409
    assert repeated.json()["detail"]["code"] == "relationship_inactive"
