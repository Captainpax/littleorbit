"""Minimal Firebase HTTP v1 client for opaque notification wake signals."""

import asyncio
from collections.abc import Callable
from pathlib import Path
from typing import Literal, Protocol, cast

import httpx
from google.auth.transport.requests import Request as GoogleAuthRequest
from google.oauth2 import service_account

PushSendResult = Literal["sent", "invalid", "retry"]
FCM_SCOPE = "https://www.googleapis.com/auth/firebase.messaging"


class RefreshableCredentials(Protocol):
    """Small credentials boundary used by the sender and deterministic tests."""

    token: str | None
    valid: bool

    def refresh(self, request: GoogleAuthRequest) -> None:
        """Refresh the short-lived OAuth access token."""


def load_credentials(path: Path) -> RefreshableCredentials:
    """Load a service-account key from the explicitly mounted private file."""

    return cast(
        RefreshableCredentials,
        service_account.Credentials.from_service_account_file(
            str(path), scopes=[FCM_SCOPE]
        ),
    )


class FcmClient:
    """Send only a content-free, high-priority wake to one Android token."""

    def __init__(
        self,
        project_id: str,
        credentials: RefreshableCredentials,
        *,
        client: httpx.AsyncClient | None = None,
        request_factory: Callable[[], GoogleAuthRequest] = GoogleAuthRequest,
    ) -> None:
        self._endpoint = f"https://fcm.googleapis.com/v1/projects/{project_id}/messages:send"
        self._credentials = credentials
        self._client = client
        self._request_factory = request_factory

    async def send_content_free(self, token: str) -> PushSendResult:
        """Send an opaque availability signal and classify retry behavior."""

        access_token = await self._access_token()
        payload = {
            "message": {
                "token": token,
                "data": {"signal": "notification.available"},
                "android": {"priority": "HIGH", "ttl": "300s"},
            }
        }
        headers = {"Authorization": f"Bearer {access_token}"}
        if self._client is not None:
            response = await self._client.post(self._endpoint, json=payload, headers=headers)
        else:
            async with httpx.AsyncClient(timeout=10) as client:
                response = await client.post(self._endpoint, json=payload, headers=headers)
        if response.status_code == 200:
            return "sent"
        return "invalid" if _is_unregistered(response) else "retry"

    async def _access_token(self) -> str:
        if not self._credentials.valid or not self._credentials.token:
            request = self._request_factory()
            await asyncio.to_thread(self._credentials.refresh, request)
        if not self._credentials.token:
            raise RuntimeError("FCM authorization did not return an access token")
        return self._credentials.token


def _is_unregistered(response: httpx.Response) -> bool:
    try:
        body = response.json()
    except ValueError:
        return False
    error = body.get("error") if isinstance(body, dict) else None
    details = error.get("details", []) if isinstance(error, dict) else []
    terminal_codes = {"UNREGISTERED", "SENDER_ID_MISMATCH"}
    return any(
        isinstance(detail, dict) and detail.get("errorCode") in terminal_codes
        for detail in details
    )
