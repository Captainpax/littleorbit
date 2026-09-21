"""Private-worker client for the isolated public-context fetcher."""

import logging
import re
import unicodedata

import httpx
from sqlalchemy import select

from .config import Settings, get_settings
from .database import SessionFactory
from .public_context_catalog import PUBLIC_CONTEXT_BY_URL
from .public_context_fetcher import PublicContextResponse
from .quiz_intelligence_models import WebContextSource

LOGGER = logging.getLogger(__name__)
_INSTRUCTION = re.compile(
    r"(?:ignore (?:all |the )?(?:previous|prior)|system prompt|developer message|"
    r"assistant\s*:|tool[_ ]?call|jailbreak|BEGIN (?:SYSTEM|INSTRUCTION)|output JSON)",
    re.IGNORECASE,
)


async def load_public_context(settings: Settings | None = None) -> list[str]:
    """Load bounded snippets only for enabled, code-owned exact sources."""

    runtime = settings or get_settings()
    if not runtime.ai_public_context_enabled:
        return []
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
            except (httpx.HTTPError, ValueError):
                LOGGER.warning("Allowlisted public context source %s was unavailable", source.key)
    return snippets


def safe_public_excerpt(value: str) -> str | None:
    """Reject control text and instruction-shaped web content before prompting."""

    normalized = unicodedata.normalize("NFKC", value).strip()
    if not normalized or _INSTRUCTION.search(normalized):
        return None
    if any(unicodedata.category(character).startswith("C") for character in normalized):
        return None
    return re.sub(r"\s+", " ", normalized)[:4_000]
