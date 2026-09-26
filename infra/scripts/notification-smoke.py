"""Exercise the isolated per-device notification and note-edit alert path."""

from __future__ import annotations

import asyncio
import json
import os
import urllib.request
from pathlib import Path
from typing import Any
from uuid import uuid4

import websockets

ROOT = Path(__file__).resolve().parents[2]
ACCOUNT_FILE = ROOT / ".inspect/smoke-accounts.json"
ORIGIN = os.environ.get("LITTLE_ORBIT_SMOKE_ORIGIN", "http://127.0.0.1:18180")
HTTP = f"{ORIGIN}/api/v1"
WS = f"{ORIGIN.replace('http://', 'ws://').replace('https://', 'wss://')}/ws/v1"
CLIENT_HEADERS = {
    "X-Little-Orbit-Client": "android",
    "X-Little-Orbit-Version-Code": "20",
}


def request_json(
    method: str, path: str, token: str, payload: object | None = None
) -> Any:
    """Send one authenticated JSON request without printing secrets or content."""

    headers = {"authorization": f"Bearer {token}", **CLIENT_HEADERS}
    body = None
    if payload is not None:
        headers["content-type"] = "application/json"
        body = json.dumps(payload).encode()
    request = urllib.request.Request(HTTP + path, data=body, headers=headers, method=method)
    with urllib.request.urlopen(request, timeout=20) as response:
        raw = response.read(2 * 1024 * 1024)
    return json.loads(raw) if raw else None


def login(email: str, password: str) -> str:
    result = request_json(
        "POST", "/auth/login", "", {"email": email, "password": password}
    )
    return str(result["access_token"])


def register_device(token: str, device_id: str) -> None:
    request_json(
        "PUT",
        f"/notification-devices/{device_id}",
        token,
        {"platform": "android", "app_version_code": 20, "notifications_enabled": True},
    )


def pending(token: str, device_id: str) -> list[dict[str, Any]]:
    return request_json("GET", f"/notifications/pending?device_id={device_id}", token)


def acknowledge_all(token: str, device_id: str) -> None:
    """Clear backfilled events for a newly registered disposable installation."""

    events = pending(token, device_id)
    if events:
        request_json(
            "POST",
            "/notifications/deliveries/ack",
            token,
            {"device_id": device_id, "event_ids": [item["id"] for item in events]},
        )


async def await_type(socket: Any, wanted: str) -> dict[str, Any]:
    for _ in range(8):
        message = json.loads(await asyncio.wait_for(socket.recv(), timeout=5))
        if message.get("type") == wanted:
            return message
    raise RuntimeError(f"WebSocket did not produce {wanted}")


async def verify_note_edit_alert(
    first_token: str, second_token: str, second_device: str
) -> None:
    baseline = sum(
        item["kind"] == "note_editing" for item in pending(second_token, second_device)
    )
    note = request_json(
        "POST",
        "/notes",
        first_token,
        {"operation_id": str(uuid4()), "title": "Notification smoke", "body": ""},
    )
    first_headers = {"Authorization": f"Bearer {first_token}", **CLIENT_HEADERS}
    second_headers = {"Authorization": f"Bearer {second_token}", **CLIENT_HEADERS}
    uri = f"{WS}/notes/{note['id']}"
    async with websockets.connect(uri, additional_headers=first_headers) as first:
        await await_type(first, "note.snapshot")
        await send_insert(first, 0, 0, "First")
        assert sum(
            item["kind"] == "note_editing"
            for item in pending(second_token, second_device)
        ) == baseline + 1
        await send_insert(first, 1, 5, " second")
        assert sum(
            item["kind"] == "note_editing"
            for item in pending(second_token, second_device)
        ) == baseline + 1
        async with websockets.connect(uri, additional_headers=second_headers) as second:
            await await_type(second, "note.snapshot")
            await send_insert(first, 2, 12, " third")
            assert sum(
                item["kind"] == "note_editing"
                for item in pending(second_token, second_device)
            ) == baseline + 1


async def send_insert(socket: Any, revision: int, position: int, text: str) -> None:
    await socket.send(
        json.dumps(
            {
                "operation_id": str(uuid4()),
                "base_revision": revision,
                "kind": "insert",
                "position": position,
                "text": text,
            }
        )
    )
    await await_type(socket, "note.ack")


async def main() -> None:
    """Verify WSS hints, per-device acks, legacy bridging, and note cooldown."""

    config = json.loads(ACCOUNT_FILE.read_text(encoding="utf-8"))
    first = login(config["accounts"][0]["email"], config["password"])
    second = login(config["accounts"][1]["email"], config["password"])
    first_device, second_device = str(uuid4()), str(uuid4())
    register_device(second, first_device)
    register_device(second, second_device)
    acknowledge_all(second, first_device)
    acknowledge_all(second, second_device)
    request_json(
        "PATCH",
        "/notification-preferences",
        second,
        {
            "master_enabled": True,
            "smooches_enabled": True,
            "note_editing_enabled": True,
            "daily_quiz_enabled": True,
            "countdowns_enabled": True,
            "together_time_enabled": True,
            "weekly_summary_enabled": True,
        },
    )
    socket_headers = {"Authorization": f"Bearer {second}", **CLIENT_HEADERS}
    async with websockets.connect(
        f"{WS}/notifications?device_id={first_device}", additional_headers=socket_headers
    ) as hints:
        await await_type(hints, "notification.ready")
        request_json("POST", "/smooches", first, {"operation_id": str(uuid4()), "emoji": "💖"})
        hint = await await_type(hints, "notification.available")
        assert hint == {"type": "notification.available"}
    first_pending = pending(second, first_device)
    second_pending = pending(second, second_device)
    assert [item["id"] for item in first_pending] == [item["id"] for item in second_pending]
    smooch_event_ids = [
        item["id"] for item in first_pending if item["kind"] == "smooch_received"
    ]
    assert len(smooch_event_ids) == 1
    request_json(
        "POST",
        "/notifications/deliveries/ack",
        second,
        {"device_id": first_device, "event_ids": smooch_event_ids},
    )
    assert not any(
        item["kind"] == "smooch_received"
        for item in pending(second, first_device)
    )
    assert sum(
        item["kind"] == "smooch_received"
        for item in pending(second, second_device)
    ) == 1
    assert request_json("GET", "/smooches/pending", second) == []
    await verify_note_edit_alert(first, second, second_device)
    remaining = pending(second, second_device)
    request_json(
        "POST",
        "/notifications/deliveries/ack",
        second,
        {"device_id": second_device, "event_ids": [item["id"] for item in remaining]},
    )
    assert pending(second, second_device) == []
    print("Per-device Smooch delivery, content-free WSS hints, and note-edit cooldown passed.")


if __name__ == "__main__":
    asyncio.run(main())
