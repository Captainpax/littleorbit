"""Create a disposable Markdown document with sanitized PNG and animated GIF images."""

from __future__ import annotations

import asyncio
import hashlib
import io
import json
import time
import urllib.request
from pathlib import Path
from typing import Any
from uuid import uuid4

import websockets
from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[2]
HTTP = "http://127.0.0.1:18180/api/v1"
WS = "ws://127.0.0.1:18180/ws/v1"
CLIENT = {"X-Little-Orbit-Client": "android", "X-Little-Orbit-Version-Code": "19"}
TITLE_FILE = ROOT / ".inspect/attachment-smoke-title.txt"


def json_request(method: str, path: str, token: str, payload: object | None = None) -> Any:
    headers = {"authorization": f"Bearer {token}", **CLIENT}
    body = None
    if payload is not None:
        headers["content-type"] = "application/json"
        body = json.dumps(payload).encode()
    request = urllib.request.Request(HTTP + path, data=body, headers=headers, method=method)
    with urllib.request.urlopen(request, timeout=20) as response:
        raw = response.read(2 * 1024 * 1024)
    return json.loads(raw) if raw else None


def upload(token: str, note_id: str, name: str, media_type: str, data: bytes) -> str:
    reserved = json_request(
        "POST",
        f"/notes/{note_id}/attachments",
        token,
        {
            "operation_id": str(uuid4()),
            "file_name": name,
            "media_type": media_type,
            "size_bytes": len(data),
            "sha256": hashlib.sha256(data).hexdigest(),
        },
    )
    attachment_id = reserved["attachment"]["id"]
    headers = {
        "authorization": f"Bearer {token}",
        "content-type": "application/octet-stream",
        "Upload-Offset": "0",
        **CLIENT,
    }
    request = urllib.request.Request(
        HTTP + f"/notes/{note_id}/attachments/{attachment_id}/content",
        data=data,
        headers=headers,
        method="PUT",
    )
    with urllib.request.urlopen(request, timeout=20):
        pass
    return str(attachment_id)


def image_bytes(image_format: str, colors: tuple[str, str]) -> bytes:
    frames = []
    for color in colors:
        frame = Image.new("RGBA", (160, 100), color)
        ImageDraw.Draw(frame).ellipse((50, 20, 110, 80), fill="#F7F6FF")
        frames.append(frame)
    output = io.BytesIO()
    if image_format == "GIF":
        frames[0].save(output, format="GIF", save_all=True, append_images=frames[1:],
                       duration=[180, 180], loop=0, disposal=2)
    else:
        frames[0].save(output, format=image_format)
    return output.getvalue()


def wait_available(token: str, note_id: str) -> None:
    for _ in range(30):
        items = json_request("GET", f"/notes/{note_id}/attachments", token)
        if items and all(item["status"] == "available" for item in items):
            return
        time.sleep(1)
    raise RuntimeError("Attachment sanitization did not finish")


async def set_markdown(token: str, note_id: str, body: str) -> None:
    headers = {"Authorization": f"Bearer {token}", **CLIENT}
    async with websockets.connect(
        f"{WS}/notes/{note_id}", additional_headers=headers
    ) as socket:
        snapshot = json.loads(await socket.recv())
        while snapshot.get("type") != "note.snapshot":
            snapshot = json.loads(await socket.recv())
        await socket.send(json.dumps({
            "operation_id": str(uuid4()), "base_revision": snapshot["revision"],
            "kind": "insert", "position": 0, "text": body,
        }))
        for _ in range(6):
            if json.loads(await socket.recv()).get("type") == "note.ack":
                return
    raise RuntimeError("Markdown edit was not acknowledged")


async def main() -> None:
    config = json.loads((ROOT / ".inspect/smoke-accounts.json").read_text(encoding="utf-8"))
    login = json_request("POST", "/auth/login", "", {
        "email": config["accounts"][0]["email"], "password": config["password"]})
    token = login["access_token"]
    title = f"Attachment smoke {uuid4().hex[:8]}"
    note = json_request("POST", "/notes", token, {
        "operation_id": str(uuid4()), "title": title, "body": ""})
    png_id = upload(token, note["id"], "transparent.png", "image/png",
                    image_bytes("PNG", ("#A89BFF", "#A89BFF")))
    gif_id = upload(token, note["id"], "transparent.gif", "image/gif",
                    image_bytes("GIF", ("#FF7D79", "#A89BFF")))
    wait_available(token, note["id"])
    body = ("# Inline private images\n\n"
            f"![Sanitized PNG](attachment://{png_id})\n\n"
            f"![Animated GIF](attachment://{gif_id})\n")
    await set_markdown(token, note["id"], body)
    TITLE_FILE.write_text(title, encoding="utf-8")
    print(f"Created {title} with inline sanitized PNG and animated GIF.")


if __name__ == "__main__":
    asyncio.run(main())
