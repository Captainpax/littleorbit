"""Deterministic safety, privacy, answerability, and duplicate gates."""

import hashlib
import re
import unicodedata
from dataclasses import dataclass
from difflib import SequenceMatcher

from .schemas import CandidateQuestion, QuestionKind

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

GENERIC_PATTERNS = (
    r"\bsomeone you trust\b",
    r"\ba new person\b",
    r"\bpeople in general\b",
)


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
    reasons = _content_reasons(candidate, normalized)
    reasons.extend(_interaction_reasons(candidate, normalized))
    if _has_layout_whitespace(candidate):
        reasons.append("layout_whitespace")
    if is_near_duplicate(candidate.prompt, recent):
        reasons.append("near_duplicate")
    return ValidationResult(not reasons, tuple(reasons), normalized_hash(candidate.prompt))


def _has_layout_whitespace(candidate: CandidateQuestion) -> bool:
    """Reject invisible or repeated spacing before content reaches any client."""

    values = [
        candidate.prompt,
        *candidate.options,
        candidate.scale_low_label or "",
        candidate.scale_high_label or "",
    ]
    for value in values:
        if value != value.strip() or "  " in value:
            return True
        for character in value:
            if _invalid_layout_character(character):
                return True
    return False


def _invalid_layout_character(character: str) -> bool:
    codepoint = ord(character)
    hidden_space = character != " " and (
        character.isspace() or unicodedata.category(character) == "Zs"
    )
    return hidden_space or codepoint < 32 or codepoint == 127


def _content_reasons(candidate: CandidateQuestion, normalized: str) -> list[str]:
    """Return policy and basic answerability failures."""

    reasons: list[str] = []
    for reason, patterns in UNSAFE_PATTERNS.items():
        if any(re.search(pattern, normalized) for pattern in patterns):
            reasons.append(reason)
    if not candidate.prompt.rstrip().endswith("?"):
        reasons.append("not_a_question")
    if any(re.search(pattern, normalized) for pattern in GENERIC_PATTERNS):
        reasons.append("not_couple_focused")
    if candidate.intimacy != (candidate.category.value == "intimacy"):
        reasons.append("intimacy_category_mismatch")
    if candidate.category.value == "intimacy" and any(
        term in normalized for term in ("must", "should agree", "owe your partner")
    ):
        reasons.append("missing_consent_boundary")
    return reasons


def _interaction_reasons(candidate: CandidateQuestion, normalized: str) -> list[str]:
    """Return failures specific to an answer interaction."""

    reasons: list[str] = []
    if candidate.kind is QuestionKind.PARTNER_GUESS and re.search(
        r"\b(your partner|partner s)\b", normalized
    ):
        reasons.append("partner_guess_not_self_answerable")
    if candidate.kind is QuestionKind.WEIGHTED and re.search(
        r"\b(scale|1 to 10|one to ten)\b", normalized
    ):
        reasons.append("scale_embedded_in_prompt")
    if any(
        normalize_question(option) in {"all of the above", "none of the above"}
        for option in candidate.options
    ):
        reasons.append("ambiguous_option")
    return reasons
