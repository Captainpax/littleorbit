"""Verify explicit note-copy recovery rewrites clean attachment ownership."""

from __future__ import annotations

import json
import re
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[2]
HTTP = "http://127.0.0.1:18180/api/v1"
CLIENT = {"X-Little-Orbit-Client": "android", "X-Little-Orbit-Version-Code": "24"}
REFERENCE = re.compile(r"attachment://([0-9a-fA-F-]{36})")


def request_json(
    method: str, path: str, token: str = "", payload: object | None = None
) -> Any:
    """Send one bounded request through the disposable smoke gateway."""

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


def main() -> None:
    """Fork the synthetic attachment note and validate retry-safe remapping."""

    config = json.loads((ROOT / ".inspect/smoke-accounts.json").read_text("utf-8"))
    login = request_json(
        "POST",
        "/auth/login",
        payload={
            "email": config["accounts"][0]["email"],
            "password": config["password"],
        },
    )
    token = str(login["access_token"])
    source_title = (ROOT / ".inspect/attachment-smoke-title.txt").read_text("utf-8")
    source = next(note for note in request_json("GET", "/notes", token) if note["title"] == source_title)
    source_ids = set(REFERENCE.findall(source["body"]))
    if len(source_ids) != 2:
        raise RuntimeError("Synthetic source did not contain both attachment mappings")

    operation_id = str(uuid4())
    payload = {
        "operation_id": operation_id,
        "title": f"{source_title} conflict copy",
        "body": source["body"],
    }
    forked = request_json("POST", f"/notes/{source['id']}/fork", token, payload)
    retried = request_json("POST", f"/notes/{source['id']}/fork", token, payload)
    forked_ids = set(REFERENCE.findall(forked["body"]))
    if forked["id"] == source["id"] or retried["id"] != forked["id"]:
        raise RuntimeError("Fork identity was not retry-safe")
    if len(forked_ids) != 2 or forked_ids & source_ids:
        raise RuntimeError("Fork did not rewrite every attachment reference")
    attachments = request_json("GET", f"/notes/{forked['id']}/attachments", token)
    if {item["id"] for item in attachments} != forked_ids:
        raise RuntimeError("Forked Markdown did not match note-owned attachments")
    if any(item["status"] != "available" for item in attachments):
        raise RuntimeError("Fork exposed an attachment before clean availability")
    invalid = dict(payload)
    invalid["operation_id"] = str(uuid4())
    invalid["body"] = f"![missing](attachment://{uuid4()})"
    try:
        request_json("POST", f"/notes/{source['id']}/fork", token, invalid)
    except urllib.error.HTTPError as error:
        if error.code != 409:
            raise
    else:
        raise RuntimeError("Fork accepted an attachment without a source-note mapping")
    print("Retry-safe note fork copied and remapped both clean attachments.")


if __name__ == "__main__":
    main()
