"""Fixed public-context HTTP boundary through a synthetic transport only."""

from unittest.mock import Mock

import httpx
import pytest
from fastapi import HTTPException

from little_orbit_api import public_context_fetcher as fetcher
from little_orbit_api.public_context_catalog import PUBLIC_CONTEXT_SOURCES


async def test_no_environment_proxy_or_redirect_and_fixed_source_only(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    real_client = httpx.AsyncClient
    requests: list[httpx.Request] = []

    def handle(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(200, headers={"content-type": "text/plain"}, content=b"Fixture")

    factory = Mock(side_effect=lambda **kwargs: real_client(
        **kwargs, transport=httpx.MockTransport(handle)))
    monkeypatch.setattr(fetcher.httpx, "AsyncClient", factory)
    monkeypatch.setenv("HTTPS_PROXY", "http://private-proxy.invalid:8080")
    body, mime = await fetcher._fetch_bounded(PUBLIC_CONTEXT_SOURCES[0])
    assert (body, mime) == (b"Fixture", "text/plain")
    assert factory.call_args.kwargs["trust_env"] is False
    assert factory.call_args.kwargs["follow_redirects"] is False
    assert len(requests) == 1 and str(requests[0].url) == PUBLIC_CONTEXT_SOURCES[0].url


@pytest.mark.parametrize("status,headers,content", [
    (302, {"location": "http://127.0.0.1/private"}, b""),
    (200, {"content-type": "image/png"}, b"Fixture"),
    (200, {"content-type": "text/plain"}, b"x" * (fetcher.MAX_RESPONSE_BYTES + 1)),
], ids=["redirect", "mime", "size"])
async def test_redirect_mime_and_body_bounds_stay_fail_closed(
    monkeypatch: pytest.MonkeyPatch, status: int, headers: dict[str, str], content: bytes,
) -> None:
    real_client = httpx.AsyncClient
    calls = Mock(return_value=httpx.Response(status, headers=headers, content=content))
    monkeypatch.setattr(fetcher.httpx, "AsyncClient", lambda **kwargs: real_client(
        **kwargs, transport=httpx.MockTransport(calls)))
    with pytest.raises(HTTPException):
        await fetcher._fetch_bounded(PUBLIC_CONTEXT_SOURCES[0])
    calls.assert_called_once()
