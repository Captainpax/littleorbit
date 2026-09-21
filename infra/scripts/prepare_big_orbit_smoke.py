"""Enable MFA for the disposable smoke owner without printing its secrets."""

from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

import pyotp

ROOT = Path(__file__).resolve().parents[2]
API = "http://127.0.0.1:18180/api"


def request_json(
    method: str, path: str, payload: object, token: str | None = None
) -> dict[str, object]:
    """Send one bounded request to the isolated smoke API."""

    headers = {"content-type": "application/json"}
    if token:
        headers["authorization"] = f"Bearer {token}"
    request = urllib.request.Request(
        f"{API}{path}",
        data=json.dumps(payload).encode(),
        headers=headers,
        method=method,
    )
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            raw = response.read(256 * 1024)
    except urllib.error.HTTPError as error:
        raise RuntimeError(f"{method} {path} failed with {error.code}") from error
    value = json.loads(raw)
    if not isinstance(value, dict):
        raise RuntimeError(f"{method} {path} returned an invalid object")
    return value


def main() -> None:
    """Log in, complete first-factor setup, and persist disposable QA material."""

    accounts = json.loads((ROOT / ".inspect/smoke-accounts.json").read_text("utf-8"))
    email = accounts["accounts"][0]["email"]
    password = accounts["password"]
    login = request_json(
        "POST", "/v1/auth/login", {"email": email, "password": password}
    )
    token = login.get("access_token")
    if not isinstance(token, str):
        raise RuntimeError("Smoke owner login did not return a session")
    enrollment = request_json(
        "POST", "/v2/admin/mfa/start", {"password": password}, token
    )
    uri = enrollment.get("otpauth_uri")
    if not isinstance(uri, str):
        raise RuntimeError("Smoke MFA enrollment did not return a URI")
    secret_values = urllib.parse.parse_qs(urllib.parse.urlparse(uri).query).get("secret")
    if not secret_values:
        raise RuntimeError("Smoke MFA enrollment URI did not contain a secret")
    secret = secret_values[0]
    confirmed = request_json(
        "POST", "/v2/admin/mfa/confirm", {"code": pyotp.TOTP(secret).now()}, token
    )
    output = {
        "api_base_url": API,
        "email": email,
        "password": password,
        "totp_secret": secret,
        "recovery_codes": confirmed.get("recovery_codes", []),
    }
    target = ROOT / ".inspect/big-orbit-smoke-admin.json"
    target.write_text(json.dumps(output, indent=2), encoding="utf-8")
    target.chmod(0o600)
    print(f"Prepared disposable Big Orbit owner in {target.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
