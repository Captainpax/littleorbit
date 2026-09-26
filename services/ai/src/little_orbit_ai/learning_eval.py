"""Deterministic promotion gate for model-proposed learning policy."""

import re

from .schemas import LearningPolicy, LearningQuestionSignal, QuestionDepth

_INSTRUCTION_SHAPED = re.compile(
    r"(?:ignore previous|system prompt|developer message|tool call|https?://|@\w+\.)",
    re.IGNORECASE,
)


def policy_rejection_reasons(
    policy: LearningPolicy, signals: list[LearningQuestionSignal]
) -> tuple[str, ...]:
    """Return stable reason codes; an empty tuple permits atomic activation."""

    reasons: list[str] = []
    if policy.schema_version != "2":
        reasons.append("legacy_schema")
    if len(policy.prefer_categories) < 3:
        reasons.append("insufficient_category_coverage")
    if set(policy.prefer_depths) != set(QuestionDepth):
        reasons.append("incomplete_depth_ladder")
    if len({item.casefold() for item in policy.guidance}) != len(policy.guidance):
        reasons.append("duplicate_guidance")
    if len({item.casefold() for item in policy.theme_guidance}) != len(
        policy.theme_guidance
    ):
        reasons.append("duplicate_theme_guidance")
    text = " ".join(
        [*policy.guidance, *policy.review_themes, *policy.theme_guidance]
    )
    if _INSTRUCTION_SHAPED.search(text):
        reasons.append("instruction_shaped_output")
    if not signals:
        reasons.append("missing_thresholded_signal")
    return tuple(reasons)
