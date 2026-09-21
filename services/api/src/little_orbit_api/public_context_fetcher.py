"""Secret-free, fixed-allowlist HTTPS fetcher for public quiz inspiration."""

import asyncio
import ipaddress
import re
import socket
from datetime import UTC, datetime
from html.parser import HTMLParser

import httpx
from fastapi import FastAPI, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field

from .public_context_catalog import PUBLIC_CONTEXT_BY_KEY, PublicContextSourceDefinition

MAX_RESPONSE_BYTES = 65_536
MAX_TEXT_CHARS = 4_000
ALLOWED_CONTENT_TYPES = ("text/html", "text/plain", "application/json")


class PublicContextResponse(BaseModel):
    """Bounded output consumed by the private quiz worker."""

    model_config = ConfigDict(extra="forbid")

    source_key: str
    source_url: str
    text: str = Field(min_length=1, max_length=MAX_TEXT_CHARS)
    fetched_at: datetime


class _VisibleTextParser(HTMLParser):
    """Extract visible prose while discarding scripts and document plumbing."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self.hidden_depth = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.casefold() in {"script", "style", "svg", "noscript"}:
            self.hidden_depth += 1

    def handle_endtag(self, tag: str) -> None:
        if tag.casefold() in {"script", "style", "svg", "noscript"}:
            self.hidden_depth = max(0, self.hidden_depth - 1)

    def handle_data(self, data: str) -> None:
        if not self.hidden_depth:
            self.parts.append(data)


app = FastAPI(
    title="Little Orbit public context fetcher",
    version="1",
    docs_url=None,
    redoc_url=None,
    openapi_url=None,
)


@app.get("/v1/health/live")
async def live() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/v1/context/{source_key}", response_model=PublicContextResponse)
async def context(source_key: str) -> PublicContextResponse:
    """Fetch one compile-time source key with no redirects or caller URL input."""

    source = PUBLIC_CONTEXT_BY_KEY.get(source_key)
    if source is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Public source is unavailable")
    await _assert_public_dns(source)
    body, content_type = await _fetch_bounded(source)
    text = _visible_text(body, content_type)
    if not text:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, "Public source contained no text")
    return PublicContextResponse(
        source_key=source.key,
        source_url=source.url,
        text=text,
        fetched_at=datetime.now(UTC),
    )


async def _assert_public_dns(source: PublicContextSourceDefinition) -> None:
    """Fail closed when an allowlisted hostname resolves to a non-public address."""

    try:
        answers = await asyncio.get_running_loop().getaddrinfo(
            source.hostname,
            443,
            type=socket.SOCK_STREAM,
        )
    except OSError as exc:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, "Public source lookup failed") from exc
    addresses = {item[4][0] for item in answers}
    if not addresses or any(not ipaddress.ip_address(value).is_global for value in addresses):
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, "Public source address was rejected")


async def _fetch_bounded(source: PublicContextSourceDefinition) -> tuple[bytes, str]:
    headers = {"User-Agent": "Little-Orbit-Public-Context/1.2 (+https://lil-orb.pax-kun.com)"}
    try:
        async with (
            httpx.AsyncClient(
                follow_redirects=False, timeout=10, headers=headers
            ) as client,
            client.stream("GET", source.url) as response,
        ):
            if response.status_code != status.HTTP_200_OK:
                raise HTTPException(
                    status.HTTP_502_BAD_GATEWAY, "Public source request was rejected"
                )
            content_type = response.headers.get("content-type", "").split(";", 1)[0].lower()
            if content_type not in ALLOWED_CONTENT_TYPES:
                raise HTTPException(
                    status.HTTP_502_BAD_GATEWAY, "Public source type was rejected"
                )
            try:
                declared = int(response.headers.get("content-length", "0") or 0)
            except ValueError as exc:
                raise HTTPException(
                    status.HTTP_502_BAD_GATEWAY,
                    "Public source length was invalid",
                ) from exc
            if declared > MAX_RESPONSE_BYTES:
                raise HTTPException(
                    status.HTTP_502_BAD_GATEWAY, "Public source response was too large"
                )
            chunks: list[bytes] = []
            total = 0
            async for chunk in response.aiter_bytes():
                total += len(chunk)
                if total > MAX_RESPONSE_BYTES:
                    raise HTTPException(
                        status.HTTP_502_BAD_GATEWAY, "Public source response was too large"
                    )
                chunks.append(chunk)
    except httpx.HTTPError as exc:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, "Public source request failed") from exc
    return b"".join(chunks), content_type


def _visible_text(body: bytes, content_type: str) -> str:
    decoded = body.decode("utf-8", errors="replace")
    if content_type == "text/html":
        parser = _VisibleTextParser()
        parser.feed(decoded)
        decoded = " ".join(parser.parts)
    text = re.sub(r"\s+", " ", decoded).strip()
    return text[:MAX_TEXT_CHARS]
