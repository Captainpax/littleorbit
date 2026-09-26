"""Password, opaque token, TOTP, recovery code, and redaction primitives."""

import base64
import hashlib
import hmac
import secrets
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from io import BytesIO
from ipaddress import ip_address
from urllib.parse import quote

import pyotp
import qrcode
import qrcode.image.svg
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerifyMismatchError
from cryptography.fernet import Fernet, InvalidToken

PASSWORD_HASHER = PasswordHasher(
    time_cost=3,
    memory_cost=65536,
    parallelism=2,
    hash_len=32,
    salt_len=16,
)


def normalize_email(email: str) -> str:
    """Normalize an email for comparisons without provider-specific rewriting."""

    return email.strip().casefold()


def hash_password(password: str) -> str:
    """Hash a password with the project's pinned Argon2id parameters."""

    return PASSWORD_HASHER.hash(password)


def verify_password(password_hash: str, password: str) -> bool:
    """Verify a password and return false for mismatches or malformed hashes."""

    try:
        return PASSWORD_HASHER.verify(password_hash, password)
    except (VerifyMismatchError, InvalidHashError):
        return False


def new_opaque_token(byte_count: int = 32) -> str:
    """Create a URL-safe token that is shown only to its intended recipient."""

    return secrets.token_urlsafe(byte_count)


def hash_token(token: str, pepper: str) -> str:
    """Create a keyed token digest safe to persist."""

    return hmac.new(pepper.encode(), token.encode(), hashlib.sha256).hexdigest()


def new_pair_code() -> str:
    """Create an unambiguous eight-character pairing code."""

    alphabet = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
    return "".join(secrets.choice(alphabet) for _ in range(8))


def new_recovery_codes(count: int = 10) -> list[str]:
    """Create one-time administrator recovery codes for display once."""

    return [f"{secrets.token_hex(3)}-{secrets.token_hex(3)}" for _ in range(count)]


def encrypt_totp_secret(secret: str, fernet_key: str) -> str:
    """Encrypt a TOTP secret before database storage."""

    return Fernet(fernet_key.encode()).encrypt(secret.encode()).decode()


def decrypt_totp_secret(ciphertext: str, fernet_key: str) -> str:
    """Decrypt a stored TOTP secret or fail closed for an invalid key/value."""

    try:
        return Fernet(fernet_key.encode()).decrypt(ciphertext.encode()).decode()
    except InvalidToken as exc:
        raise ValueError("TOTP secret could not be decrypted") from exc


def totp_uri(secret: str, email: str) -> str:
    """Build the enrollment URI used by authenticator QR applications."""

    return pyotp.TOTP(secret).provisioning_uri(name=quote(email), issuer_name="Little Orbit")


def qr_svg_data_url(value: str) -> str:
    """Render an enrollment value as an inline SVG QR data URL."""

    image = qrcode.make(value, image_factory=qrcode.image.svg.SvgPathImage)
    output = BytesIO()
    image.save(output)
    encoded = base64.b64encode(output.getvalue()).decode()
    return f"data:image/svg+xml;base64,{encoded}"


def qr_png_data_url(value: str) -> str:
    """Render an authenticator value as an in-memory PNG usable by Android ImageView."""

    image = qrcode.make(value)
    output = BytesIO()
    image.save(output)
    encoded = base64.b64encode(output.getvalue()).decode()
    return f"data:image/png;base64,{encoded}"


def verify_totp(secret: str, code: str, now: datetime, last_counter: int | None) -> int | None:
    """Verify with one-window clock skew and reject replayed counters."""

    totp = pyotp.TOTP(secret)
    for offset in (-1, 0, 1):
        candidate_time = now.timestamp() + offset * totp.interval
        counter = int(candidate_time // totp.interval)
        if last_counter is not None and counter <= last_counter:
            continue
        if hmac.compare_digest(totp.at(int(candidate_time)), code):
            return counter
    return None


@dataclass(frozen=True)
class ClientAddress:
    """Resolved network address and whether proxy headers were trusted."""

    address: str
    forwarded: bool


def resolve_client_address(
    peer: str, forwarded_for: str | None, trusted_proxy: str
) -> ClientAddress:
    """Trust one valid forwarded address only from one valid configured peer."""

    canonical_peer = validated_ip_address(peer)
    canonical_proxy = validated_ip_address(trusted_proxy)
    canonical_forwarded = validated_ip_address(forwarded_for)
    if (
        canonical_peer is not None
        and canonical_peer == canonical_proxy
        and canonical_forwarded is not None
    ):
        return ClientAddress(canonical_forwarded, True)
    return ClientAddress(canonical_peer or "unknown", False)


def validated_ip_address(value: str | None) -> str | None:
    """Return one canonical IP address or reject malformed gateway metadata."""

    if not value:
        return None
    candidate = value.strip()
    try:
        return str(ip_address(candidate))
    except ValueError:
        return None


def redact_config(values: Mapping[str, object]) -> dict[str, object]:
    """Redact keys likely to contain credentials before returning configuration."""

    markers = ("secret", "password", "token", "key", "credential")
    return {
        key: "[redacted]" if any(marker in key.casefold() for marker in markers) else value
        for key, value in values.items()
    }
