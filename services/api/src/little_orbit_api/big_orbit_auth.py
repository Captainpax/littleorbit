"""P-256 device binding and short Big Orbit administrator sessions."""

import base64
import hashlib
import hmac
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import cast
from uuid import UUID

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from .admin_device_models import (
    AdminDevice,
    AdminDeviceChallenge,
    AdminDeviceSession,
)
from .big_orbit_schemas import DeviceChallengeResponse
from .clock import SystemClock
from .config import Settings
from .models import Account, AdminMfa, Session
from .security import (
    decrypt_totp_secret,
    hash_password,
    hash_token,
    new_opaque_token,
    verify_password,
    verify_totp,
)

CHALLENGE_LIFETIME = timedelta(minutes=5)
DEVICE_CREDENTIAL_LIFETIME = timedelta(days=90)
_DUMMY_ADMIN_HASH = hash_password("timing-only-big-orbit-password")


@dataclass(frozen=True)
class IssuedAdminSession:
    """Raw short credential and its persisted session identity."""

    token: str
    session_id: UUID
    expires_at: datetime


async def authenticate_admin(
    session: AsyncSession,
    email: str,
    password: str,
    totp_code: str | None,
    recovery_code: str | None,
    settings: Settings,
) -> Account:
    """Verify account and one replay-safe MFA proof under the account lock."""

    account = await session.scalar(
        select(Account)
        .where(Account.email_normalized == email)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    password_ok = verify_password(
        account.password_hash if account is not None else _DUMMY_ADMIN_HASH,
        password,
    )
    if not password_ok or not _active_admin(account) or account is None:
        raise _invalid_credentials()
    mfa = await session.get(AdminMfa, account.id, with_for_update=True)
    if mfa is None or mfa.enabled_at is None:
        raise _invalid_credentials()
    if not _verify_factor(mfa, totp_code, recovery_code, settings):
        raise _invalid_credentials()
    return account


async def issue_device_session(
    session: AsyncSession,
    account: Account,
    device: AdminDevice,
    settings: Settings,
) -> IssuedAdminSession:
    """Issue an ordinary short session and persist its exact device binding."""

    now = SystemClock().now()
    raw = new_opaque_token()
    expires = now + timedelta(minutes=settings.admin_session_minutes)
    record = Session(
        account_id=account.id,
        token_hash=hash_token(raw, settings.token_pepper.get_secret_value()),
        expires_at=expires,
        authenticated_at=now,
        admin_mfa_verified=True,
        created_at=now,
    )
    session.add(record)
    await session.flush()
    session.add(
        AdminDeviceSession(session_id=record.id, device_id=device.id, created_at=now)
    )
    device.last_seen_at = now
    return IssuedAdminSession(raw, record.id, expires)


async def create_device_challenge(
    session: AsyncSession,
    device: AdminDevice | None,
    purpose: str,
    settings: Settings,
) -> DeviceChallengeResponse:
    """Create one hashed challenge, including indistinguishable decoys."""

    now = SystemClock().now()
    raw = new_opaque_token(32)
    record = AdminDeviceChallenge(
        device_id=device.id if device else None,
        challenge_hash=hash_token(raw, settings.token_pepper.get_secret_value()),
        purpose=purpose,
        expires_at=now + CHALLENGE_LIFETIME,
        created_at=now,
    )
    session.add(record)
    await session.flush()
    return DeviceChallengeResponse(
        challenge_id=record.id,
        challenge=raw,
        expires_at=record.expires_at,
    )


async def create_enrollment_device(
    session: AsyncSession,
    account: Account,
    label: str,
    public_key_spki: str,
) -> AdminDevice:
    """Stage one key after validating exact P-256 SPKI bytes."""

    der, _ = _public_key(public_key_spki)
    fingerprint = hashlib.sha256(der).hexdigest()
    existing = await session.scalar(
        select(AdminDevice)
        .where(
            AdminDevice.account_id == account.id,
            AdminDevice.key_fingerprint == fingerprint,
        )
        .with_for_update()
    )
    if existing is not None and existing.approved_at is not None and existing.revoked_at is None:
        raise HTTPException(status.HTTP_409_CONFLICT, "This device is already enrolled")
    if existing is not None:
        existing.label = label
        existing.public_key_spki = public_key_spki
        existing.approved_at = None
        existing.revoked_at = None
        existing.credential_hash = None
        existing.credential_expires_at = None
        return existing
    record = AdminDevice(
        account_id=account.id,
        label=label,
        public_key_spki=public_key_spki,
        key_fingerprint=fingerprint,
        created_at=SystemClock().now(),
    )
    session.add(record)
    await session.flush()
    return record


async def consume_signed_challenge(
    session: AsyncSession,
    device: AdminDevice,
    challenge_id: UUID,
    challenge: str,
    signature: str,
    purpose: str,
    settings: Settings,
) -> None:
    """Consume the exact challenge only after validating its device signature."""

    now = SystemClock().now()
    record = await session.scalar(
        select(AdminDeviceChallenge)
        .where(AdminDeviceChallenge.id == challenge_id)
        .with_for_update()
    )
    expected = hash_token(challenge, settings.token_pepper.get_secret_value())
    valid = (
        record is not None
        and record.device_id == device.id
        and record.purpose == purpose
        and record.consumed_at is None
        and record.expires_at > now
        and hmac.compare_digest(record.challenge_hash, expected)
        and verify_device_signature(device, purpose, challenge_id, challenge, signature)
    )
    if not valid or record is None:
        raise _invalid_device_proof()
    record.consumed_at = now


def verify_device_signature(
    device: AdminDevice,
    purpose: str,
    challenge_id: UUID,
    challenge: str,
    signature: str,
) -> bool:
    """Verify Android Keystore ECDSA over a canonical domain-separated message."""

    try:
        _, key = _public_key(device.public_key_spki)
        signature_bytes = base64.b64decode(signature, validate=True)
        message = canonical_challenge(purpose, challenge_id, challenge).encode()
        key.verify(signature_bytes, message, ec.ECDSA(hashes.SHA256()))
        return True
    except (ValueError, InvalidSignature):
        return False


def canonical_challenge(purpose: str, challenge_id: UUID, challenge: str) -> str:
    """Return the byte-exact string signed by Big Orbit."""

    return f"big-orbit:{purpose}:{challenge_id}:{challenge}"


def approve_device(device: AdminDevice, settings: Settings) -> tuple[str, datetime]:
    """Approve enrollment and rotate the one-time-displayed device credential."""

    now = SystemClock().now()
    raw = new_opaque_token(48)
    expires = now + DEVICE_CREDENTIAL_LIFETIME
    device.approved_at = now
    device.credential_hash = hash_token(raw, settings.token_pepper.get_secret_value())
    device.credential_expires_at = expires
    device.last_seen_at = now
    return raw, expires


def credential_valid(device: AdminDevice, raw: str, settings: Settings) -> bool:
    """Validate a long-lived device credential independently of the key proof."""

    now = SystemClock().now()
    supplied = hash_token(raw, settings.token_pepper.get_secret_value())
    return bool(
        device.approved_at
        and device.revoked_at is None
        and device.credential_hash
        and device.credential_expires_at
        and device.credential_expires_at > now
        and hmac.compare_digest(device.credential_hash, supplied)
    )


def _public_key(value: str) -> tuple[bytes, ec.EllipticCurvePublicKey]:
    try:
        der = base64.b64decode(value, validate=True)
        loaded = serialization.load_der_public_key(der)
    except (ValueError, TypeError) as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Invalid device key") from exc
    if not isinstance(loaded, ec.EllipticCurvePublicKey) or not isinstance(
        loaded.curve, ec.SECP256R1
    ):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Invalid device key")
    return der, cast(ec.EllipticCurvePublicKey, loaded)


def _verify_factor(
    mfa: AdminMfa,
    totp_code: str | None,
    recovery_code: str | None,
    settings: Settings,
) -> bool:
    now = SystemClock().now()
    if totp_code:
        if settings.totp_encryption_key is None:
            return False
        secret = decrypt_totp_secret(
            mfa.encrypted_secret,
            settings.totp_encryption_key.get_secret_value(),
        )
        counter = verify_totp(secret, totp_code, now, mfa.last_accepted_counter)
        if counter is not None:
            mfa.last_accepted_counter = counter
            mfa.updated_at = now
            return True
    if recovery_code:
        digest = hash_token(recovery_code, settings.token_pepper.get_secret_value())
        if digest in mfa.recovery_hashes:
            mfa.recovery_hashes = [item for item in mfa.recovery_hashes if item != digest]
            mfa.updated_at = now
            return True
    return False


def _active_admin(account: Account | None) -> bool:
    return bool(
        account
        and account.is_admin
        and account.verified_at is not None
        and account.suspended_at is None
        and account.deleted_at is None
    )


def _invalid_credentials() -> HTTPException:
    return HTTPException(status.HTTP_401_UNAUTHORIZED, "Administrator credentials are invalid")


def _invalid_device_proof() -> HTTPException:
    return HTTPException(status.HTTP_401_UNAUTHORIZED, "Device proof is invalid or expired")
