"""Exercise a shared note through two disposable paired client sessions."""

from __future__ import annotations

import asyncio
import json
import urllib.request
from pathlib import Path
from typing import Any
from uuid import uuid4

import websockets

ROOT = Path(__file__).resolve().parents[2]
HTTP = "http://127.0.0.1:18180/api/v1"
WS = "ws://127.0.0.1:18180/ws/v1"
CLIENT = {"X-Little-Orbit-Client": "android", "X-Little-Orbit-Version-Code": "19"}


def request_json(
    method: str, path: str, token: str = "", payload: object | None = None
) -> Any:
    """Send one bounded request through the isolated smoke gateway."""

    headers = dict(CLIENT)
    if token:
        headers["authorization"] = f"Bearer {token}"
    body = None
    if payload is not None:
        headers["content-type"] = "application/json"
        body = json.dumps(payload).encode()
    request = urllib.request.Request(HTTP + path, data=body, headers=headers, method=method)
    with urllib.request.urlopen(request, timeout=20) as response:
        raw = response.read(2 * 1024 * 1024)
    return json.loads(raw) if raw else None


def login(email: str, password: str) -> str:
    """Create one disposable authenticated session without printing its token."""

    response = request_json(
        "POST", "/auth/login", payload={"email": email, "password": password}
    )
    return str(response["access_token"])


async def receive(
    socket: Any, message_type: str, operation_id: str | None = None
) -> dict[str, Any]:
    """Wait for one matching message while ignoring presence changes."""

    async with asyncio.timeout(15):
        while True:
            message = json.loads(await socket.recv())
            if message.get("type") != message_type:
                continue
            if operation_id is None or message.get("operation_id") == operation_id:
                return message


async def edit(
    sender: Any,
    observers: tuple[Any, ...],
    revision: int,
    position: int,
    value: str,
) -> dict[str, Any]:
    """Send one insert and require the same acknowledgement on every observer."""

    operation_id = str(uuid4())
    await sender.send(
        json.dumps(
            {
                "operation_id": operation_id,
                "base_revision": revision,
                "kind": "insert",
                "position": position,
                "text": value,
            }
        )
    )
    messages = await asyncio.gather(
        *(receive(socket, "note.ack", operation_id) for socket in observers)
    )
    bodies = {message["body"] for message in messages}
    revisions = {message["revision"] for message in messages}
    if len(bodies) != 1 or len(revisions) != 1:
        raise RuntimeError("Paired clients received different note acknowledgements")
    return messages[0]


async def main() -> None:
    """Create, edit, disconnect, reconnect, and verify one shared document."""

    config = json.loads((ROOT / ".inspect/smoke-accounts.json").read_text(encoding="utf-8"))
    tokens = [
        login(account["email"], config["password"]) for account in config["accounts"]
    ]
    initial = "Shared from A 🪐"
    note = request_json(
        "POST",
        "/notes",
        tokens[0],
        {"operation_id": str(uuid4()), "title": "Paired sync smoke", "body": initial},
    )
    note_id = str(note["id"])
    partner_list = request_json("GET", "/notes", tokens[1])
    if not any(item["id"] == note_id and item["body"] == initial for item in partner_list):
        raise RuntimeError("Partner could not list the newly created document")

    headers = [{"Authorization": f"Bearer {token}", **CLIENT} for token in tokens]
    async with websockets.connect(
        f"{WS}/notes/{note_id}", additional_headers=headers[0]
    ) as first:
        await receive(first, "note.snapshot")
        async with websockets.connect(
            f"{WS}/notes/{note_id}", additional_headers=headers[1]
        ) as second:
            await receive(second, "note.snapshot")
            combined = await edit(first, (first, second), 0, len(initial), " + live A")
        disconnected = await edit(
            first,
            (first,),
            int(combined["revision"]),
            len(str(combined["body"])),
            " + offline B",
        )
        async with websockets.connect(
            f"{WS}/notes/{note_id}", additional_headers=headers[1]
        ) as second:
            snapshot = await receive(second, "note.snapshot")
            if snapshot["body"] != disconnected["body"]:
                raise RuntimeError("Reconnect snapshot missed the disconnected edit")
            final = await edit(
                second,
                (first, second),
                int(snapshot["revision"]),
                len(str(snapshot["body"])),
                " + live B",
            )

    for token in tokens:
        notes = request_json("GET", "/notes", token)
        match = next((item for item in notes if item["id"] == note_id), None)
        if match is None or match["body"] != final["body"] or match["revision"] != 3:
            raise RuntimeError("Final shared snapshot did not converge")
    print("Paired note creation, live edits, reconnect, and reverse edit converged.")


if __name__ == "__main__":
    asyncio.run(main())
