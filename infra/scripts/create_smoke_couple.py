"""Create and pair two disposable accounts in the isolated smoke stack."""

from __future__ import annotations

import json
import re
import subprocess
import time
import urllib.error
import urllib.request
from pathlib import Path
from uuid import uuid4

API = "http://127.0.0.1:18180/api/v1"
MAILPIT = "http://127.0.0.1:18025/api/v1"
PASSWORD = "Smoke-Orbit-Only-2026!"
ROOT = Path(__file__).resolve().parents[2]
TOKEN_PATTERN = re.compile(r"#token=([A-Za-z0-9_-]{32,})")


def request_json(
    method: str, url: str, payload: object | None = None, token: str | None = None
) -> object:
    """Send one bounded JSON request and decode its response."""

    body = None if payload is None else json.dumps(payload).encode()
    headers = {"content-type": "application/json"}
    if token:
        headers["authorization"] = f"Bearer {token}"
    request = urllib.request.Request(url, data=body, headers=headers, method=method)
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            raw = response.read(2 * 1024 * 1024)
    except urllib.error.HTTPError as error:
        raise RuntimeError(f"{method} {url} failed with {error.code}") from error
    if not raw:
        return {}
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return {"message": raw.decode(errors="replace")}


def deliver_mail() -> None:
    """Run one mail-outbox delivery inside the isolated API container."""

    code = (
        "import asyncio; from little_orbit_api.config import get_settings; "
        "from little_orbit_api.mail import deliver_pending_mail; "
        "asyncio.run(deliver_pending_mail(get_settings()))"
    )
    subprocess.run(
        [
            "docker", "compose", "--env-file", str(ROOT / ".env"),
            "-f", str(ROOT / "infra/compose.yaml"),
            "-f", str(ROOT / "infra/compose.dev.yaml"),
            "-f", str(ROOT / "infra/compose.smoke.yaml"),
            "exec", "-T", "api", "python", "-c", code,
        ],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )


def verification_tokens() -> dict[str, str]:
    """Read verification links only from the disposable local Mailpit."""

    result = request_json("GET", f"{MAILPIT}/messages")
    messages = result.get("messages", []) if isinstance(result, dict) else []
    tokens: dict[str, str] = {}
    for message in messages:
        message_id = message.get("ID")
        detail = request_json("GET", f"{MAILPIT}/message/{message_id}")
        text = json.dumps(detail)
        match = TOKEN_PATTERN.search(text.replace("\\u0026", "&"))
        recipients = message.get("To", [])
        address = recipients[0].get("Address") if recipients else None
        if address and match:
            tokens[address.lower()] = match.group(1)
    return tokens


def register(email: str, display_name: str) -> None:
    request_json(
        "POST",
        f"{API}/auth/register",
        {
            "email": email,
            "password": PASSWORD,
            "display_name": display_name,
            "is_adult": True,
            "accepted_terms_version": "2026-09-10",
            "website": "",
        },
    )


def login(email: str) -> str:
    result = request_json(
        "POST", f"{API}/auth/login", {"email": email, "password": PASSWORD}
    )
    if not isinstance(result, dict) or not isinstance(result.get("access_token"), str):
        raise RuntimeError("Smoke login did not return a session")
    return result["access_token"]


def main() -> None:
    """Create, verify, login, and atomically pair two isolated accounts."""

    suffix = f"{int(time.time())}-{uuid4().hex[:6]}"
    accounts = [
        (f"smoke-a-{suffix}@example.com", "Orbit Smoke A"),
        (f"smoke-b-{suffix}@example.com", "Orbit Smoke B"),
    ]
    request_json("DELETE", f"{MAILPIT}/messages")
    for email, name in accounts:
        register(email, name)
    deliver_mail()
    tokens = verification_tokens()
    for email, _ in accounts:
        request_json("POST", f"{API}/auth/verify", {"token": tokens[email]})
    sessions = [login(email) for email, _ in accounts]
    code = request_json("POST", f"{API}/pairing/codes", {}, sessions[0])["code"]
    request_json("POST", f"{API}/pairing/redeem", {"code": code}, sessions[1])
    pending = request_json("GET", f"{API}/pairing/pending", token=sessions[0])
    request_json(
        "POST",
        f"{API}/pairing/confirm",
        {"request_id": pending["request_id"]},
        sessions[0],
    )
    output = {
        "api_base_url": API.removesuffix("/v1"),
        "password": PASSWORD,
        "accounts": [{"email": email, "display_name": name} for email, name in accounts],
    }
    target = ROOT / ".inspect/smoke-accounts.json"
    target.parent.mkdir(exist_ok=True)
    target.write_text(json.dumps(output, indent=2), encoding="utf-8")
    print(f"Created paired disposable accounts in {target.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
