"""Notification contract and foreground-hint regression tests."""

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from pydantic import ValidationError

from little_orbit_api.main import create_app
from little_orbit_api.notification_hub import NotificationConnectionHub
from little_orbit_api.notification_schemas import (
    NotificationDeliveryAck,
    NotificationDeviceUpsert,
    NotificationEventResponse,
    NotificationPreferencesUpdate,
)


def test_notification_routes_are_part_of_the_versioned_api() -> None:
    """Release builds must expose polling, preferences, devices, and the WSS hint."""

    paths = {getattr(route, "path", "") for route in create_app().routes}
    assert "/v1/notification-preferences" in paths
    assert "/v1/notification-devices/{device_id}" in paths
    assert "/v1/notifications/pending" in paths
    assert "/v1/notifications/deliveries/ack" in paths
    assert "/v1/notifications" in paths


def test_notification_requests_are_bounded_and_strict() -> None:
    """Unknown fields, unsupported platforms, and oversized acks fail closed."""

    with pytest.raises(ValidationError):
        NotificationDeviceUpsert(
            platform="ios", app_version_code=17, notifications_enabled=True  # type: ignore[arg-type]
        )
    with pytest.raises(ValidationError):
        NotificationDeliveryAck(device_id=uuid4(), event_ids=[uuid4()] * 51)
    with pytest.raises(ValidationError):
        NotificationPreferencesUpdate.model_validate(
            {
                "master_enabled": True,
                "smooches_enabled": True,
                "note_editing_enabled": True,
                "daily_quiz_enabled": True,
                "countdowns_enabled": True,
                "weekly_summary_enabled": True,
                "unexpected": True,
            }
        )


def test_event_contract_contains_metadata_without_note_content() -> None:
    """Document alerts may identify the document but never include its body."""

    now = datetime.now(UTC)
    event = NotificationEventResponse(
        id=uuid4(),
        kind="note_editing",
        created_at=now,
        expires_at=now + timedelta(hours=24),
        actor_display_name="Partner",
        note_id=uuid4(),
        note_title="Weekend ideas",
    )
    assert "body" not in event.model_dump()
    assert "attachment" not in event.model_dump()


@pytest.mark.asyncio
async def test_foreground_hint_is_content_free_and_prunes_failed_socket() -> None:
    """The WSS signal carries no relationship data and forgets failed sockets."""

    hub = NotificationConnectionHub()
    account_id = uuid4()
    healthy = AsyncMock()
    failed = AsyncMock()
    failed.send_json.side_effect = RuntimeError("closed")
    hub.add(account_id, healthy)
    hub.add(account_id, failed)

    await hub.available(account_id)
    await hub.available(account_id)

    healthy.send_json.assert_awaited_with({"type": "notification.available"})
    assert healthy.send_json.await_count == 2
    assert failed.send_json.await_count == 1
