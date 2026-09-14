"""Notification contract and foreground-hint regression tests."""

from datetime import UTC, date, datetime, timedelta
from types import SimpleNamespace
from typing import cast
from unittest.mock import AsyncMock
from uuid import UUID, uuid4

import pytest
from fastapi import HTTPException, status
from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from little_orbit_api.main import create_app
from little_orbit_api.models import CoupleMember
from little_orbit_api.notification_hub import NotificationConnectionHub
from little_orbit_api.notification_schemas import (
    NotificationDeliveryAck,
    NotificationDeviceUpsert,
    NotificationEventResponse,
    NotificationKind,
    NotificationPreferencesUpdate,
)
from little_orbit_api.routes import notifications as notification_routes


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


@pytest.mark.parametrize(
    ("kind", "countdown_id", "countdown_title", "quiz_date"),
    [
        ("countdown_created", uuid4(), "Cabin", None),
        ("countdown_rescheduled", uuid4(), "Cabin", None),
        ("quiz_available", None, None, date(2026, 9, 13)),
        ("quiz_partner_finished", None, None, date(2026, 9, 13)),
        ("quiz_results_ready", None, None, date(2026, 9, 13)),
    ],
)
def test_rc13_event_contract_accepts_bounded_countdown_and_quiz_metadata(
    kind: NotificationKind,
    countdown_id: UUID | None,
    countdown_title: str | None,
    quiz_date: date | None,
) -> None:
    """RC13 transition alerts identify only the relevant date or shared countdown."""

    now = datetime.now(UTC)
    event = NotificationEventResponse(
        id=uuid4(),
        kind=kind,
        created_at=now,
        expires_at=now + timedelta(hours=24),
        actor_display_name="Partner",
        countdown_id=countdown_id,
        countdown_title=countdown_title,
        quiz_date=quiz_date,
    )
    payload = event.model_dump(mode="json")
    assert "answer" not in payload
    assert "notes" not in payload


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


@pytest.mark.asyncio
async def test_unavailable_quiz_does_not_block_other_pending_events(monkeypatch: pytest.MonkeyPatch) -> None:
    """A missing daily pool cannot turn the shared notification inbox into a 503."""

    class Nested:
        async def __aenter__(self) -> None: return None
        async def __aexit__(self, *args: object) -> None: return None

    session = SimpleNamespace(begin_nested=lambda: Nested())
    monkeypatch.setattr(
        notification_routes,
        "materialize_day",
        AsyncMock(side_effect=HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE)),
    )
    member = SimpleNamespace(couple_id=uuid4())

    await notification_routes._ensure_quiz_alert(
        cast(AsyncSession, session), cast(CoupleMember, member), uuid4()
    )
