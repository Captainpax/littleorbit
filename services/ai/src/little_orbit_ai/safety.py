"""Deterministic safety, privacy, answerability, and duplicate gates."""

import hashlib
import re
import unicodedata
from dataclasses import dataclass
from difflib import SequenceMatcher

from .schemas import CandidateQuestion

UNSAFE_PATTERNS: dict[str, tuple[str, ...]] = {
    "identifying_information": (
        r"\b(address|phone number|email address|full legal name|social security)\b",
        r"\bwhere (exactly )?do you live\b",
    ),
    "coercion_or_manipulation": (r"\b(force|pressure|punish|control|track them secretly)\b",),
    "regulated_advice": (r"\b(diagnose|medical advice|legal advice|financial advice)\b",),
    "self_harm": (r"\b(suicide|self[- ]harm|kill yourself)\b",),
    "minors": (r"\b(child sexual|minor sexual|underage)\b",),
    "graphic_sexual": (r"\b(explicit sex act|graphic sexual)\b",),
    "unsafe_location": (r"\b(real[- ]time location|secretly locate|gps coordinates)\b",),
}


@dataclass(frozen=True)
class ValidationResult:
    """Machine-auditable decision without storing private content."""

    accepted: bool
    reasons: tuple[str, ...]
    normalized_hash: str


def normalize_question(text: str) -> str:
    """Normalize question text for stable exact duplicate detection."""

    folded = unicodedata.normalize("NFKC", text).casefold()
    return " ".join(re.sub(r"[^\w\s]", " ", folded).split())


def normalized_hash(text: str) -> str:
    """Return a stable SHA-256 digest of normalized public question text."""

    return hashlib.sha256(normalize_question(text).encode()).hexdigest()


def is_near_duplicate(candidate: str, recent: list[str], threshold: float = 0.9) -> bool:
    """Return true for highly similar normalized wording.

    PostgreSQL trigram similarity is authoritative in production. This pure gate
    protects local evaluation and remains deterministic across outages.
    """

    normalized = normalize_question(candidate)
    return any(
        SequenceMatcher(None, normalized, normalize_question(item)).ratio() >= threshold
        for item in recent
    )


def validate_candidate(candidate: CandidateQuestion, recent: list[str]) -> ValidationResult:
    """Apply deterministic safety and answerability gates to one candidate."""

    normalized = normalize_question(candidate.prompt)
    reasons: list[str] = []
    for reason, patterns in UNSAFE_PATTERNS.items():
        if any(re.search(pattern, normalized) for pattern in patterns):
            reasons.append(reason)
    if not candidate.prompt.rstrip().endswith("?"):
        reasons.append("not_a_question")
    if is_near_duplicate(candidate.prompt, recent):
        reasons.append("near_duplicate")
    if candidate.category.value == "intimacy" and any(
        term in normalized for term in ("must", "should agree", "owe your partner")
    ):
        reasons.append("missing_consent_boundary")
    return ValidationResult(not reasons, tuple(reasons), normalized_hash(candidate.prompt))
