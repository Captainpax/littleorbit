"""PostgreSQL integration tests for encrypted installation push addressing."""

import asyncio
import os
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest
import pytest_asyncio
from cryptography.fernet import Fernet
from pydantic import SecretStr
from sqlalchemy import func, inspect, select, text

pytestmark = [
    pytest.mark.skipif(
        not os.getenv("LITTLE_ORBIT_TEST_DATABASE_URL"),
        reason="set LITTLE_ORBIT_TEST_DATABASE_URL to an isolated PostgreSQL database",
    ),
    pytest.mark.asyncio(loop_scope="session"),
]

from little_orbit_api.config import Settings  # noqa: E402
from little_orbit_api.database import Base, SessionFactory, engine  # noqa: E402
from little_orbit_api.interaction_models import Smooch  # noqa: E402
from little_orbit_api.models import Account, Couple, CoupleMember  # noqa: E402
from little_orbit_api.notification_models import (  # noqa: E402
    NotificationDelivery,
    NotificationDevice,
    NotificationEvent,
)
from little_orbit_api.push_delivery import (  # noqa: E402
    ClaimedPush,
    _claim_pending,
    _record_result,
)
from little_orbit_api.push_tokens import (  # noqa: E402
    assign_push_token,
    decrypt_push_token,
    push_token_hash,
)


@pytest_asyncio.fixture(autouse=True, loop_scope="session")
async def clean_database() -> None:
    """Keep destructive push checks inside the named isolated database."""

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
        password_hash="unused-in-push-tests",
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
        push_failure_count=0,
    )


async def _seed_delivery() -> tuple[NotificationDevice, NotificationEvent]:
    sender = _account("first@example.com")
    recipient = _account("second@example.com")
    now = datetime.now(UTC)
    couple = Couple(
        id=uuid4(),
        proximity_threshold_m=100,
        proximity_algorithm_version=2,
        home_timezone="America/Los_Angeles",
        created_at=now,
        updated_at=now,
    )
    device = _device(recipient.id)
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
        session.add_all([sender, recipient, couple])
        session.add_all(
            [
                CoupleMember(
                    couple_id=couple.id,
                    account_id=account.id,
                    joined_at=now,
                    intimacy_enabled=False,
                    location_enabled=False,
                )
                for account in (sender, recipient)
            ]
        )
        await session.commit()
    async with SessionFactory() as session:
        session.add_all([device, smooch, event])
        await session.flush()
        session.add(
            NotificationDelivery(event_id=event.id, device_id=device.id, created_at=now)
        )
        await session.commit()
    return device, event


def _push_settings() -> Settings:
    return Settings.model_validate(
        {
            "token_pepper": SecretStr("notification-push-test-pepper"),
            "push_token_encryption_key": SecretStr(Fernet.generate_key().decode()),
        }
    )


async def test_stale_fcm_result_cannot_clear_rotated_token() -> None:
    """A delayed response is bound to the exact claimed token generation."""

    account = _account("push@example.com")
    device = _device(account.id)
    settings = _push_settings()
    claimed_at = datetime.now(UTC)
    old_token = "old-device-address-with-enough-entropy"
    new_token = "new-device-address-with-enough-entropy"
    async with SessionFactory() as session:
        session.add_all([account, device])
        await session.flush()
        assert await assign_push_token(session, device, old_token, claimed_at, settings)
        device.push_last_attempt_at = claimed_at
        await session.commit()
    old_claim = ClaimedPush(
        device.id,
        device.push_token_encrypted or "",
        push_token_hash(old_token, settings),
        claimed_at,
    )
    async with SessionFactory() as session:
        current = await session.get(NotificationDevice, device.id, with_for_update=True)
        assert current is not None
        assert await assign_push_token(
            session, current, new_token, claimed_at + timedelta(seconds=1), settings
        )
        await session.commit()

    await _record_result(old_claim, "invalid", claimed_at + timedelta(seconds=2))
    async with SessionFactory() as session:
        current = await session.get(NotificationDevice, device.id)
        assert current is not None and current.push_token_encrypted is not None
        assert decrypt_push_token(current.push_token_encrypted, settings) == new_token
        assert current.push_token_hash == push_token_hash(new_token, settings)


async def test_unchanged_fcm_heartbeat_preserves_an_in_flight_claim() -> None:
    """A routine registration heartbeat cannot reopen or supersede push work."""

    account = _account("stable-push@example.com")
    device = _device(account.id)
    settings = _push_settings()
    claimed_at = datetime.now(UTC)
    token = "stable-device-address-with-enough-entropy"
    async with SessionFactory() as session:
        session.add_all([account, device])
        await session.flush()
        assert await assign_push_token(session, device, token, claimed_at, settings)
        device.push_last_attempt_at = claimed_at
        device.push_last_success_at = claimed_at
        ciphertext = device.push_token_encrypted
        await session.commit()
    async with SessionFactory() as session:
        current = await session.get(NotificationDevice, device.id, with_for_update=True)
        assert current is not None
        assert await assign_push_token(
            session, current, token, claimed_at + timedelta(minutes=15), settings
        )
        await session.commit()
        assert current.push_token_encrypted == ciphertext
        assert current.push_last_attempt_at == claimed_at
        assert current.push_last_success_at == claimed_at


async def test_concurrent_push_assignment_moves_one_token_without_a_unique_race() -> None:
    """Two installation heartbeats serialize ownership of one Firebase address."""

    account = _account("concurrent-push@example.com")
    first = _device(account.id)
    second = _device(account.id)
    settings = _push_settings()
    token = "concurrently-assigned-device-address-with-enough-entropy"
    release = asyncio.Event()
    ready = [asyncio.Event(), asyncio.Event()]
    async with SessionFactory() as session:
        session.add_all([account, first, second])
        await session.commit()

    async def assign(device_id: UUID, index: int) -> None:
        async with SessionFactory() as session:
            current = await session.get(NotificationDevice, device_id, with_for_update=True)
            assert current is not None
            ready[index].set()
            await release.wait()
            assert await assign_push_token(
                session, current, token, datetime.now(UTC), settings
            )
            await session.commit()

    tasks = [
        asyncio.create_task(assign(first.id, 0)),
        asyncio.create_task(assign(second.id, 1)),
    ]
    await asyncio.gather(*(event.wait() for event in ready))
    release.set()
    await asyncio.gather(*tasks)

    async with SessionFactory() as session:
        digest = push_token_hash(token, settings)
        owner_count = await session.scalar(
            select(func.count())
            .select_from(NotificationDevice)
            .where(NotificationDevice.push_token_hash == digest)
        )
    assert owner_count == 1


async def test_push_claim_contains_only_installation_delivery_state() -> None:
    """The sender claims an opaque token generation while polling stays authoritative."""

    device, _ = await _seed_delivery()
    settings = _push_settings()
    now = datetime.now(UTC)
    token = "claimed-device-address-with-enough-entropy"
    async with SessionFactory() as session:
        current = await session.get(NotificationDevice, device.id, with_for_update=True)
        assert current is not None
        assert await assign_push_token(session, current, token, now, settings)
        await session.commit()

    claims = await _claim_pending(now + timedelta(seconds=1))

    assert len(claims) == 1
    assert claims[0].device_id == device.id
    assert claims[0].token_hash == push_token_hash(token, settings)
    assert set(vars(claims[0])) == {
        "device_id",
        "encrypted_token",
        "token_hash",
        "claimed_at",
    }
    succeeded_at = now + timedelta(seconds=2)
    await _record_result(claims[0], "sent", succeeded_at)
    async with SessionFactory() as session:
        current = await session.get(NotificationDevice, device.id)
        assert current is not None
        assert current.push_last_success_at == succeeded_at
        assert current.push_failure_count == 0


async def test_invalid_fcm_token_stays_rejected_until_rotation() -> None:
    """An explicitly dead address cannot be re-added on every polling heartbeat."""

    account = _account("invalid-push@example.com")
    device = _device(account.id)
    settings = _push_settings()
    now = datetime.now(UTC)
    dead = "dead-device-address-with-enough-entropy"
    fresh = "fresh-device-address-with-enough-entropy"
    async with SessionFactory() as session:
        session.add_all([account, device])
        await session.flush()
        assert await assign_push_token(session, device, dead, now, settings)
        device.push_last_attempt_at = now
        await session.commit()
    claim = ClaimedPush(
        device.id,
        device.push_token_encrypted or "",
        push_token_hash(dead, settings),
        now,
    )
    await _record_result(claim, "invalid", now + timedelta(seconds=1))

    async with SessionFactory() as session:
        current = await session.get(NotificationDevice, device.id, with_for_update=True)
        assert current is not None
        assert not await assign_push_token(session, current, dead, now, settings)
        assert await assign_push_token(session, current, fresh, now, settings)
        await session.commit()
        assert current.push_token_encrypted is not None
