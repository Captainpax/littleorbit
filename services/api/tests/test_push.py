"""Privacy and failure behavior for optional content-free FCM wakes."""

import json
from typing import cast

import httpx
from cryptography.fernet import Fernet
from pydantic import SecretStr

from little_orbit_api.config import Settings
from little_orbit_api.fcm import FcmClient, RefreshableCredentials
from little_orbit_api.push_tokens import decrypt_push_token, encrypt_push_token, push_token_hash


class FakeCredentials:
    """Deterministic OAuth credentials that never contact Google."""

    token: str | None = "short-lived-access-token"
    valid = True

    def refresh(self, request: object) -> None:
        raise AssertionError("valid credentials must not refresh")


def _settings() -> Settings:
    return Settings.model_validate(
        {
            "token_pepper": SecretStr("test-only-push-pepper"),
            "push_token_encryption_key": SecretStr(Fernet.generate_key().decode()),
        }
    )


def test_push_tokens_are_encrypted_and_domain_hashed() -> None:
    settings = _settings()
    token = "example-registration-token-with-enough-entropy"
    encrypted = encrypt_push_token(token, settings)

    assert encrypted is not None and token not in encrypted
    assert decrypt_push_token(encrypted, settings) == token
    assert push_token_hash(token, settings) != token
    assert decrypt_push_token("corrupt", settings) is None


async def test_fcm_payload_contains_only_an_opaque_wake_signal() -> None:
    captured: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured.update(json.loads(request.content))
        assert request.headers["Authorization"] == "Bearer short-lived-access-token"
        return httpx.Response(200, json={"name": "message-id"})

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http:
        client = FcmClient(
            "test-project",
            cast(RefreshableCredentials, FakeCredentials()),
            client=http,
        )
        result = await client.send_content_free("private-device-address")

    assert result == "sent"
    assert captured == {
        "message": {
            "token": "private-device-address",
            "data": {"signal": "notification.available"},
            "android": {"priority": "HIGH", "ttl": "300s"},
        }
    }


async def test_fcm_only_invalidates_an_explicitly_unregistered_token() -> None:
    responses = iter(
        [
            httpx.Response(
                404,
                json={
                    "error": {
                        "details": [
                            {
                                "@type": "type.googleapis.com/google.firebase.fcm.v1.FcmError",
                                "errorCode": "UNREGISTERED",
                            }
                        ]
                    }
                },
            ),
            httpx.Response(404, json={"error": {"status": "NOT_FOUND"}}),
        ]
    )

    def handler(request: httpx.Request) -> httpx.Response:
        return next(responses)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http:
        client = FcmClient(
            "test-project",
            cast(RefreshableCredentials, FakeCredentials()),
            client=http,
        )
        assert await client.send_content_free("first-device-token") == "invalid"
        assert await client.send_content_free("second-device-token") == "retry"


async def test_fcm_invalidates_a_token_owned_by_another_sender() -> None:
    """A project-mismatched address is terminal while credential failures retry."""

    response = httpx.Response(
        403,
        json={
            "error": {
                "details": [
                    {
                        "@type": "type.googleapis.com/google.firebase.fcm.v1.FcmError",
                        "errorCode": "SENDER_ID_MISMATCH",
                    }
                ]
            }
        },
    )

    async with httpx.AsyncClient(
        transport=httpx.MockTransport(lambda request: response)
    ) as http:
        client = FcmClient(
            "test-project",
            cast(RefreshableCredentials, FakeCredentials()),
            client=http,
        )
        assert await client.send_content_free("wrong-project-device-token") == "invalid"
