"""Fail-closed sanitization for explicitly consented product reviews."""

import re
import unicodedata
from dataclasses import dataclass

_URL = re.compile(r"(?:https?://|www\.)\S+", re.IGNORECASE)
_EMAIL = re.compile(r"\b[^\s@]{1,64}@[^\s@]{1,255}\b", re.IGNORECASE)
_PHONE = re.compile(r"(?<!\d)(?:\+?\d[\d .()\-]{7,}\d)(?!\d)")
_INSTRUCTION = re.compile(
    r"(?:ignore (?:all |the )?(?:previous|prior)|system prompt|developer message|"
    r"assistant\s*:|tool[_ ]?call|jailbreak|<script|BEGIN (?:SYSTEM|INSTRUCTION))",
    re.IGNORECASE,
)
_IDENTIFYING_PATTERNS = (_URL, _EMAIL, _PHONE)


@dataclass(frozen=True)
class SanitizedReview:
    """Accepted text or a bounded reason safe to expose to its author."""

    text: str | None
    status: str


def sanitize_review(review: str | None, consent: bool) -> SanitizedReview:
    """Normalize benign prose and reject text that cannot be safely de-identified."""

    if review is None:
        return SanitizedReview(None, "none")
    if not consent:
        return SanitizedReview(None, "consent_required")
    normalized = unicodedata.normalize("NFKC", review).strip()
    if not normalized or len(normalized) > 300:
        return SanitizedReview(None, "rejected")
    if _has_disallowed_control(normalized):
        return SanitizedReview(None, "rejected")
    if any(pattern.search(normalized) is not None for pattern in _IDENTIFYING_PATTERNS):
        return SanitizedReview(None, "rejected")
    if _INSTRUCTION.search(normalized):
        return SanitizedReview(None, "rejected")
    normalized = re.sub(r"[ \t]+", " ", normalized)
    normalized = re.sub(r"\s*\n\s*", " ", normalized)
    return SanitizedReview(normalized, "accepted")


def _has_disallowed_control(value: str) -> bool:
    return any(
        unicodedata.category(character).startswith("C")
        and character not in "\n\r\t"
        for character in value
    )
