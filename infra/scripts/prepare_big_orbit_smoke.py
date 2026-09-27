"""Enable MFA for the disposable smoke owner without printing its secrets."""

from __future__ import annotations

import base64
import json
import re
import subprocess
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

import pyotp
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec

ROOT = Path(__file__).resolve().parents[2]
API = "http://127.0.0.1:18180/api"
PIN_PATTERN = re.compile(r"^Big Orbit bootstrap PIN: ([0-9]{8})$", re.MULTILINE)


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
    """Use the supported PIN/key bootstrap and persist disposable QA material."""

    accounts = json.loads((ROOT / ".inspect/smoke-accounts.json").read_text("utf-8"))
    email = accounts["accounts"][0]["email"]
    password = accounts["password"]
    secret, recovery_codes = bootstrap_first_factor(email, password)
    output = {
        "api_base_url": API,
        "email": email,
        "password": password,
        "totp_secret": secret,
        "recovery_codes": recovery_codes,
    }
    target = ROOT / ".inspect/big-orbit-smoke-admin.json"
    target.write_text(json.dumps(output, indent=2), encoding="utf-8")
    target.chmod(0o600)
    print(f"Prepared disposable Big Orbit owner in {target.relative_to(ROOT)}")


def bootstrap_first_factor(email: str, password: str) -> tuple[str, list[object]]:
    """Complete first-factor setup and revoke the ephemeral bootstrap device."""

    private_key = ec.generate_private_key(ec.SECP256R1())
    started = start_bootstrap(email, password, issue_pin(email), private_key)
    token = required_string(started, "setup_token")
    proof = prove_bootstrap_device(started, private_key, token)
    if proof.get("completed") is not False:
        raise RuntimeError("Smoke owner already has MFA; reset the disposable stack")
    enrollment = required_object(required_object(proof, "status"), "mfa_enrollment")
    secret = enrollment_secret(enrollment)
    confirmed = request_json(
        "POST",
        "/v2/admin/bootstrap/mfa/confirm",
        {"code": pyotp.TOTP(secret).now()},
        token,
    )
    revoke_bootstrap_device(confirmed)
    recovery_codes = confirmed.get("recovery_codes")
    if not isinstance(recovery_codes, list):
        raise RuntimeError("Smoke MFA confirmation omitted recovery codes")
    return secret, recovery_codes


def start_bootstrap(
    email: str,
    password: str,
    pin: str,
    private_key: ec.EllipticCurvePrivateKey,
) -> dict[str, object]:
    """Consume the PIN while staging one in-memory-keyed disposable device."""

    public_key = base64.b64encode(
        private_key.public_key().public_bytes(
            serialization.Encoding.DER,
            serialization.PublicFormat.SubjectPublicKeyInfo,
        )
    ).decode()
    return request_json(
        "POST",
        "/v2/admin/bootstrap/session",
        {
            "email": email,
            "password": password,
            "pin": pin,
            "device_label": "Disposable smoke bootstrap",
            "enrollment_public_key": public_key,
        },
    )


def prove_bootstrap_device(
    started: dict[str, object],
    private_key: ec.EllipticCurvePrivateKey,
    token: str,
) -> dict[str, object]:
    """Sign the exact bootstrap challenge without persisting the private key."""

    challenge = required_object(started, "challenge")
    challenge_id = required_string(challenge, "challenge_id")
    raw_challenge = required_string(challenge, "challenge")
    signature = private_key.sign(
        f"big-orbit:bootstrap:{challenge_id}:{raw_challenge}".encode(),
        ec.ECDSA(hashes.SHA256()),
    )
    return request_json(
        "POST",
        "/v2/admin/bootstrap/device-confirm",
        {
            "challenge_id": challenge_id,
            "challenge": raw_challenge,
            "signature": base64.b64encode(signature).decode(),
        },
        token,
    )


def enrollment_secret(enrollment: dict[str, object]) -> str:
    """Extract only the disposable TOTP seed from a valid enrollment URI."""

    uri = enrollment.get("otpauth_uri")
    if not isinstance(uri, str):
        raise RuntimeError("Smoke MFA enrollment did not return a URI")
    secret_values = urllib.parse.parse_qs(urllib.parse.urlparse(uri).query).get("secret")
    if not secret_values:
        raise RuntimeError("Smoke MFA enrollment URI did not contain a secret")
    return secret_values[0]


def revoke_bootstrap_device(confirmed: dict[str, object]) -> None:
    """Remove the disposable Python key after it enables the smoke factor."""

    access_token = required_string(confirmed, "access_token")
    device_id = required_string(confirmed, "device_id")
    request_json("DELETE", f"/v2/admin/devices/{device_id}", {}, access_token)


def issue_pin(email: str) -> str:
    """Capture the one-use PIN from the isolated API without echoing it."""

    command = [
        "docker",
        "compose",
        "--env-file",
        str(ROOT / ".env"),
        "-f",
        str(ROOT / "infra/compose.yaml"),
        "-f",
        str(ROOT / "infra/compose.dev.yaml"),
        "-f",
        str(ROOT / "infra/compose.smoke.yaml"),
        "exec",
        "-T",
        "api",
        "python",
        "-m",
        "little_orbit_api.cli",
        "bootstrap-admin",
        email,
    ]
    result = subprocess.run(command, capture_output=True, text=True, check=False)
    if result.returncode != 0:
        raise RuntimeError("Smoke bootstrap PIN command failed")
    match = PIN_PATTERN.search(result.stdout)
    if match is None:
        raise RuntimeError("Smoke bootstrap PIN command returned an invalid response")
    return match.group(1)


def required_object(value: dict[str, object], key: str) -> dict[str, object]:
    """Read one required response object without dumping secret-bearing payloads."""

    candidate = value.get(key)
    if not isinstance(candidate, dict):
        raise RuntimeError(f"Smoke bootstrap response omitted {key}")
    return candidate


def required_string(value: dict[str, object], key: str) -> str:
    """Read one required response string without dumping secret-bearing payloads."""

    candidate = value.get(key)
    if not isinstance(candidate, str) or not candidate:
        raise RuntimeError(f"Smoke bootstrap response omitted {key}")
    return candidate


if __name__ == "__main__":
    main()
