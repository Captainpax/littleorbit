"""Strict, versioned model-output schemas."""

from datetime import date
from enum import StrEnum
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class QuestionKind(StrEnum):
    """Supported answer interactions across every client."""

    SINGLE = "single_choice"
    MULTIPLE = "multiple_choice"
    FREE_TEXT = "free_text"
    PARTNER_GUESS = "partner_guess"
    WEIGHTED = "weighted_scale"


class Category(StrEnum):
    """Safe, broad 1.0 question categories."""

    EVERYDAY = "everyday"
    MEMORIES = "memories"
    DREAMS = "dreams"
    VALUES = "values"
    PLAYFUL = "playful"
    CONNECTION = "connection"
    INTIMACY = "intimacy"


class CandidateQuestion(BaseModel):
    """One untrusted model candidate before deterministic validation."""

    model_config = ConfigDict(extra="forbid")

    client_id: str = Field(pattern=r"^[a-z0-9-]{3,48}$")
    kind: QuestionKind
    prompt: str = Field(min_length=12, max_length=240)
    category: Category
    intimacy: bool
    options: list[str] = Field(max_length=8)

    @model_validator(mode="after")
    def validate_shape(self) -> "CandidateQuestion":
        """Enforce option and intimacy fields that vary by kind."""

        option_kinds = {QuestionKind.SINGLE, QuestionKind.MULTIPLE, QuestionKind.PARTNER_GUESS}
        if self.kind in option_kinds and not 2 <= len(self.options) <= 8:
            raise ValueError("choice questions require 2-8 options")
        if self.kind not in option_kinds and self.options:
            raise ValueError("free text and weighted scale questions have no options")
        if len(set(self.options)) != len(self.options):
            raise ValueError("options must be unique")
        if any(not option.strip() or len(option) > 80 for option in self.options):
            raise ValueError("options must contain 1-80 visible characters")
        if self.intimacy != (self.category is Category.INTIMACY):
            raise ValueError("intimacy flag must match the intimacy category")
        return self


class GeneratedChoiceQuestion(CandidateQuestion):
    """Generated choice question with options encoded in its JSON Schema."""

    kind: Literal[
        QuestionKind.SINGLE,
        QuestionKind.MULTIPLE,
        QuestionKind.PARTNER_GUESS,
    ]
    options: list[str] = Field(min_length=2, max_length=8)


class GeneratedOpenQuestion(CandidateQuestion):
    """Generated free-text or weighted question with an empty option list."""

    kind: Literal[QuestionKind.FREE_TEXT, QuestionKind.WEIGHTED]
    options: list[str] = Field(max_length=0)


GeneratedCandidate = Annotated[
    GeneratedChoiceQuestion | GeneratedOpenQuestion,
    Field(discriminator="kind"),
]


class GeneratedBatch(BaseModel):
    """One strict calendar-date response from the local model."""

    model_config = ConfigDict(extra="forbid")

    schema_version: str = Field(pattern=r"^1$")
    date: date
    questions: list[GeneratedCandidate] = Field(min_length=5, max_length=12)


class PublishedPool(BaseModel):
    """Validated publishable questions and reproducibility metadata."""

    date: date
    general: list[CandidateQuestion] = Field(min_length=5, max_length=5)
    intimacy_alternatives: list[CandidateQuestion]
    prompt_version: str
    model: str
    model_manifest_digest: str
    fallback_reason: str | None = None
