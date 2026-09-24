"""Private-worker client for the isolated public-context fetcher."""

import hashlib
import logging
import re
import unicodedata
from dataclasses import dataclass
from datetime import timedelta

import httpx
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert

from .clock import SystemClock
from .config import Settings, get_settings
from .database import SessionFactory
from .public_context_catalog import PUBLIC_CONTEXT_BY_URL
from .public_context_fetcher import PublicContextResponse
from .quiz_intelligence_models import WebContextSnapshot, WebContextSource

LOGGER = logging.getLogger(__name__)
_INSTRUCTION = re.compile(
    r"(?:ignore (?:all |the )?(?:previous|prior)|system prompt|developer message|"
    r"assistant\s*:|tool[_ ]?call|jailbreak|BEGIN (?:SYSTEM|INSTRUCTION)|output JSON)",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class PublicContextBundle:
    """Sanitized snippets plus content-free freshness and provenance metadata."""

    snippets: list[str]
    digest: str
    stale_sources: tuple[str, ...]


async def load_public_context(settings: Settings | None = None) -> list[str]:
    """Load bounded snippets only for enabled, code-owned exact sources."""

    return (await load_public_context_bundle(settings)).snippets


async def load_public_context_bundle(
    settings: Settings | None = None,
) -> PublicContextBundle:
    """Fetch exact sources and use only snapshots younger than thirty days on outage."""

    runtime = settings or get_settings()
    if not runtime.ai_public_context_enabled:
        return PublicContextBundle([], hashlib.sha256(b"").hexdigest(), ())
    async with SessionFactory() as session:
        enabled_urls = set(
            await session.scalars(
                select(WebContextSource.base_url).where(
                    WebContextSource.enabled.is_(True),
                    WebContextSource.code_owned.is_(True),
                )
            )
        )
    sources = [
        definition
        for url, definition in PUBLIC_CONTEXT_BY_URL.items()
        if url in enabled_urls
    ]
    snippets: list[str] = []
    stale: list[str] = []
    async with httpx.AsyncClient(
        base_url=runtime.public_context_fetcher_url,
        timeout=12,
    ) as client:
        for source in sources:
            try:
                response = await client.get(f"/v1/context/{source.key}")
                response.raise_for_status()
                item = PublicContextResponse.model_validate(response.json())
                if item.source_url != source.url or item.source_key != source.key:
                    raise ValueError("public context identity mismatch")
                excerpt = safe_public_excerpt(item.text)
                if excerpt is not None:
                    snippets.append(f"{source.key}: {excerpt}")
                    await _store_snapshot(source.key, source.url, excerpt)
            except (httpx.HTTPError, ValueError):
                LOGGER.warning("Allowlisted public context source %s was unavailable", source.key)
                fallback = await _latest_snapshot(source.key)
                stale.append(source.key)
                if fallback is not None:
                    snippets.append(f"{source.key}: {fallback}")
    digest = hashlib.sha256("\n".join(sorted(snippets)).encode()).hexdigest()
    return PublicContextBundle(snippets, digest, tuple(stale))


async def _store_snapshot(source_key: str, source_url: str, excerpt: str) -> None:
    """Persist sanitized public text only; raw fetched bytes never enter the database."""

    now = SystemClock().now()
    digest = hashlib.sha256(excerpt.encode()).hexdigest()
    async with SessionFactory() as session:
        await session.execute(
            insert(WebContextSnapshot)
            .values(
                source_key=source_key,
                source_url=source_url,
                content_digest=digest,
                excerpt=excerpt,
                fetched_at=now,
                expires_at=now + timedelta(days=30),
            )
            .on_conflict_do_update(
                constraint="uq_web_context_snapshot_digest",
                set_={"fetched_at": now, "expires_at": now + timedelta(days=30)},
            )
        )
        await session.commit()


async def _latest_snapshot(source_key: str) -> str | None:
    """Return only a still-valid sanitized snapshot for one fixed source key."""

    async with SessionFactory() as session:
        return await session.scalar(
            select(WebContextSnapshot.excerpt)
            .where(
                WebContextSnapshot.source_key == source_key,
                WebContextSnapshot.expires_at > SystemClock().now(),
            )
            .order_by(WebContextSnapshot.fetched_at.desc())
            .limit(1)
        )


def safe_public_excerpt(value: str) -> str | None:
    """Reject control text and instruction-shaped web content before prompting."""

    normalized = unicodedata.normalize("NFKC", value).strip()
    if not normalized or _INSTRUCTION.search(normalized):
        return None
    if any(unicodedata.category(character).startswith("C") for character in normalized):
        return None
    return re.sub(r"\s+", " ", normalized)[:4_000]
