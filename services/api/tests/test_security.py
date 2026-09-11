"""Security primitive regression tests."""

from datetime import UTC, datetime

import pyotp

from little_orbit_api.security import (
    hash_password,
    hash_token,
    new_pair_code,
    redact_config,
    resolve_client_address,
    validated_ip_address,
    verify_password,
    verify_totp,
)


def test_argon2id_password_hash_is_salted_and_verifiable() -> None:
    left = hash_password("correct horse battery staple")
    right = hash_password("correct horse battery staple")
    assert left != right
    assert left.startswith("$argon2id$v=19$m=65536,t=3,p=2$")
    assert verify_password(left, "correct horse battery staple")
    assert not verify_password(left, "wrong")


def test_token_hash_is_keyed_and_pair_codeing_code_is_unambiguous() -> None:
    assert hash_token("same", "one") != hash_token("same", "two")
    code = new_pair_code()
    assert len(code) == 8
    assert not set(code).intersection({"0", "1", "I", "O"})


def test_forwarded_address_is_only_trusted_from_configured_peer() -> None:
    trusted = resolve_client_address("192.168.50.6", "203.0.113.9, 10.0.0.1", "192.168.50.6")
    spoofed = resolve_client_address("192.168.50.99", "203.0.113.9", "192.168.50.6")
    assert (trusted.address, trusted.forwarded) == ("203.0.113.9", True)
    assert (spoofed.address, spoofed.forwarded) == ("192.168.50.99", False)


def test_gateway_address_requires_one_valid_ip() -> None:
    assert validated_ip_address(" 203.0.113.9 ") == "203.0.113.9"
    assert validated_ip_address("203.0.113.9, 10.0.0.1") is None
    assert validated_ip_address("not-an-address") is None


def test_totp_rejects_replay_in_same_counter() -> None:
    secret = pyotp.random_base32()
    now = datetime(2026, 9, 10, 12, 0, tzinfo=UTC)
    code = pyotp.TOTP(secret).at(now)
    accepted_counter = verify_totp(secret, code, now, None)
    assert accepted_counter is not None
    assert verify_totp(secret, code, now, accepted_counter) is None


def test_config_redacts_sensitive_names() -> None:
    output = redact_config({"smtp_host": "mail", "session_secret": "x", "api_key": "y"})
    assert output == {"smtp_host": "mail", "session_secret": "[redacted]", "api_key": "[redacted]"}
