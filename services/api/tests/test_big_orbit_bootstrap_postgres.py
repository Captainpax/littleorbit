"""Optional PostgreSQL proof for one-use PIN, device proof, and first MFA."""

import base64
import os
from datetime import UTC, datetime
from uuid import UUID, uuid4

import pyotp
import pytest
import pytest_asyncio
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from fastapi import HTTPException
from pydantic import SecretStr
from sqlalchemy import func, inspect, select, text

pytestmark = [
    pytest.mark.skipif(
        not os.getenv("LITTLE_ORBIT_TEST_DATABASE_URL"),
        reason="set LITTLE_ORBIT_TEST_DATABASE_URL to an isolated PostgreSQL database",
    ),
    pytest.mark.asyncio(loop_scope="session"),
]

from little_orbit_api.admin_device_models import (  # noqa: E402
    AdminBootstrapCredential,
    AdminBootstrapSession,
    AdminDevice,
)
from little_orbit_api.big_orbit_auth import (  # noqa: E402
    canonical_challenge,
    consume_signed_challenge,
    create_device_challenge,
)
from little_orbit_api.big_orbit_bootstrap import (  # noqa: E402
    bootstrap_principal,
    bootstrap_status,
    complete_bootstrap,
    enable_bootstrap_mfa,
    issue_bootstrap_pin,
    start_bootstrap,
)
from little_orbit_api.big_orbit_schemas import BootstrapCompletion  # noqa: E402
from little_orbit_api.config import Settings, get_settings  # noqa: E402
from little_orbit_api.database import Base, SessionFactory, engine  # noqa: E402
from little_orbit_api.models import Account, AdminMfa, Session  # noqa: E402
from little_orbit_api.security import decrypt_totp_secret, hash_password  # noqa: E402


@pytest_asyncio.fixture(autouse=True, loop_scope="session")
async def clean_database() -> None:
    async with engine.begin() as connection:
        existing = set(await connection.run_sync(lambda sync: inspect(sync).get_table_names()))
        quote = connection.dialect.identifier_preparer.quote
        tables = ", ".join(
            quote(table.name) for table in Base.metadata.sorted_tables if table.name in existing
        )
        await connection.execute(text(f"TRUNCATE TABLE {tables} RESTART IDENTITY CASCADE"))


def _owner_fixture() -> tuple[Account, ec.EllipticCurvePrivateKey, str]:
    """Create disposable owner and device identities without shared secrets."""

    now = datetime.now(UTC)
    account = Account(
        id=uuid4(),
        email_normalized="owner@example.com",
        password_hash=hash_password("valid-password-123"),
        display_name="Owner",
        is_adult=True,
        accepted_terms_version="2026-09-10",
        verified_at=now,
        is_admin=True,
        created_at=now,
        updated_at=now,
    )
    private = ec.generate_private_key(ec.SECP256R1())
    public_der = private.public_key().public_bytes(
        serialization.Encoding.DER,
        serialization.PublicFormat.SubjectPublicKeyInfo,
    )
    return account, private, base64.b64encode(public_der).decode()


def _bootstrap_signature(
    private: ec.EllipticCurvePrivateKey, challenge_id: UUID, challenge: str
) -> str:
    message = canonical_challenge("bootstrap", challenge_id, challenge).encode()
    signature = private.sign(message, ec.ECDSA(hashes.SHA256()))
    return base64.b64encode(signature).decode()


async def _complete_first_mfa(
    runtime: Settings,
    setup_token: str,
    challenge_id: UUID,
    challenge: str,
    signature: str,
) -> BootstrapCompletion:
    """Prove the device, enable first-owner MFA, and complete one setup capability."""

    async with SessionFactory() as session:
        setup, account, device = await bootstrap_principal(session, setup_token, runtime)
        await consume_signed_challenge(
            session, device, challenge_id, challenge, signature, "bootstrap", runtime
        )
        setup.device_confirmed_at = datetime.now(UTC)
        status = await bootstrap_status(session, setup, account, runtime)
        assert status.mfa_enrollment is not None
        assert status.mfa_enrollment.qr_png_data_url.startswith("data:image/png;base64,")
        mfa = await session.get(AdminMfa, account.id, with_for_update=True)
        assert mfa is not None and mfa.pending_encrypted_secret is not None
        assert runtime.totp_encryption_key is not None
        key = runtime.totp_encryption_key.get_secret_value()
        secret = decrypt_totp_secret(mfa.pending_encrypted_secret, key)
        codes = await enable_bootstrap_mfa(
            session, setup, account, pyotp.TOTP(secret).now(), runtime
        )
        completion = await complete_bootstrap(
            session, setup, account, device, runtime, codes
        )
        await session.commit()
        return completion


async def _recover_completed_bootstrap(
    runtime: Settings,
    setup_token: str,
    private: ec.EllipticCurvePrivateKey,
) -> BootstrapCompletion:
    """Re-prove the same key before rotating credentials after a lost response."""

    async with SessionFactory() as session:
        setup, account, device = await bootstrap_principal(
            session, setup_token, runtime, allow_completed=True
        )
        challenge = await create_device_challenge(
            session, device, "bootstrap", runtime
        )
        signature = _bootstrap_signature(
            private, challenge.challenge_id, challenge.challenge
        )
        await consume_signed_challenge(
            session,
            device,
            challenge.challenge_id,
            challenge.challenge,
            signature,
            "bootstrap",
            runtime,
        )
        completion = await complete_bootstrap(
            session, setup, account, device, runtime
        )
        await session.commit()
        return completion


async def test_pin_is_consumed_before_device_bound_first_mfa() -> None:
    encryption_key = Fernet.generate_key().decode()
    runtime = get_settings().model_copy(
        update={"totp_encryption_key": SecretStr(encryption_key)}
    )
    account, private, public_spki = _owner_fixture()
    async with SessionFactory() as session:
        session.add(account)
        await session.flush()
        pin = await issue_bootstrap_pin(session, account, runtime)
        await session.commit()
    async with SessionFactory() as session:
        started = await start_bootstrap(
            session,
            account.email_normalized,
            "valid-password-123",
            pin,
            "Owner phone",
            public_spki,
            runtime,
        )
        challenge = await create_device_challenge(
            session, started.device, "bootstrap", runtime
        )
        await session.commit()
    signature = _bootstrap_signature(private, challenge.challenge_id, challenge.challenge)
    completion = await _complete_first_mfa(
        runtime, started.token, challenge.challenge_id, challenge.challenge, signature
    )
    assert completion.device_id == started.device.id
    assert completion.recovery_codes
    recovered = await _recover_completed_bootstrap(runtime, started.token, private)
    assert recovered.device_credential != completion.device_credential
    assert recovered.access_token != completion.access_token
    async with SessionFactory() as session:
        credential = await session.scalar(select(AdminBootstrapCredential))
        stored_setup = await session.scalar(select(AdminBootstrapSession))
        inspected_device = await session.get(AdminDevice, completion.device_id)
        assert credential is not None and credential.consumed_at is not None
        assert stored_setup is not None and stored_setup.completed_at is not None
        assert inspected_device is not None and inspected_device.approved_at is not None
        assert await session.scalar(select(func.count()).select_from(Session)) == 2
    async with SessionFactory() as session:
        locked_account = await session.get(Account, account.id, with_for_update=True)
        assert locked_account is not None
        await issue_bootstrap_pin(session, locked_account, runtime)
        await session.commit()
    async with SessionFactory() as session:
        with pytest.raises(HTTPException) as expired:
            await bootstrap_principal(
                session, started.token, runtime, allow_completed=True
            )
        assert getattr(expired.value, "status_code", None) == 401


async def test_new_pin_invalidates_unfinished_bootstrap() -> None:
    runtime = get_settings().model_copy(
        update={"totp_encryption_key": SecretStr(Fernet.generate_key().decode())}
    )
    account, _, public_spki = _owner_fixture()
    async with SessionFactory() as session:
        session.add(account)
        await session.flush()
        first_pin = await issue_bootstrap_pin(session, account, runtime)
        await session.commit()
    async with SessionFactory() as session:
        first = await start_bootstrap(
            session,
            account.email_normalized,
            "valid-password-123",
            first_pin,
            "Owner phone",
            public_spki,
            runtime,
        )
        await session.commit()
    async with SessionFactory() as session:
        stored = await session.get(Account, account.id, with_for_update=True)
        assert stored is not None
        second_pin = await issue_bootstrap_pin(session, stored, runtime)
        await session.commit()
    assert second_pin.isdigit() and len(second_pin) == 8
    async with SessionFactory() as session:
        with pytest.raises(HTTPException) as rejected:
            await bootstrap_principal(session, first.token, runtime)
        assert getattr(rejected.value, "status_code", None) == 401
