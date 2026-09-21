"""Strict, versioned model-output schemas for public question generation."""

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
    WEIGHTED = "weighted_choice"


class Category(StrEnum):
    """Safe, broad 1.0 question categories."""

    EVERYDAY = "everyday"
    MEMORIES = "memories"
    DREAMS = "dreams"
    VALUES = "values"
    PLAYFUL = "playful"
    CONNECTION = "connection"
    INTIMACY = "intimacy"


class IconKey(StrEnum):
    """Small audited icon vocabulary implemented by every client."""

    HEART = "heart"
    CHAT = "chat"
    HOME = "home"
    MEAL = "meal"
    MOVIE = "movie"
    MUSIC = "music"
    OUTDOORS = "outdoors"
    PLAY = "play"
    REST = "rest"
    STAR = "star"
    TRAVEL = "travel"
    SURPRISE = "surprise"


class CandidateQuestion(BaseModel):
    """One untrusted model candidate before deterministic validation."""

    model_config = ConfigDict(extra="forbid")

    client_id: str = Field(pattern=r"^[a-z0-9-]{3,48}$")
    kind: QuestionKind
    prompt: str = Field(min_length=12, max_length=240)
    category: Category
    intimacy: bool
    options: list[str] = Field(default_factory=list, max_length=6)
    option_icons: list[IconKey] = Field(default_factory=list, max_length=6)
    scale_low_label: str | None = Field(default=None, min_length=1, max_length=32)
    scale_high_label: str | None = Field(default=None, min_length=1, max_length=32)
    concept_family: str = Field(default="", pattern=r"^[a-z0-9-]{0,80}$")
    concept_summary: str = Field(default="", max_length=180)

    @model_validator(mode="after")
    def validate_shape(self) -> "CandidateQuestion":
        """Enforce interaction-specific option, icon, scale, and consent fields."""

        self._validate_options()
        self._validate_scale()
        return self

    def _validate_options(self) -> None:
        """Validate bounded, unique options and their audited icon keys."""

        self._validate_option_count()
        if len(self.option_icons) != len(self.options):
            raise ValueError("every option requires one audited icon key")
        normalized = {item.casefold().strip() for item in self.options}
        if len(normalized) != len(self.options):
            raise ValueError("options must be unique after normalization")
        if any(not option.strip() or len(option.strip()) > 64 for option in self.options):
            raise ValueError("options must contain 1-64 visible characters")

    def _validate_option_count(self) -> None:
        """Apply the interaction-specific option count."""

        choices = {QuestionKind.SINGLE, QuestionKind.MULTIPLE, QuestionKind.PARTNER_GUESS}
        option_kind = self.kind in choices or self.kind is QuestionKind.WEIGHTED
        upper = 5 if self.kind is QuestionKind.WEIGHTED else 6
        if option_kind and not 2 <= len(self.options) <= upper:
            raise ValueError("choice interactions require 2-6 options")
        if not option_kind and self.options:
            raise ValueError("free-text questions cannot contain options")

    def _validate_scale(self) -> None:
        """Require two distinct anchors only for weighted choices."""

        has_anchors = self.scale_low_label is not None and self.scale_high_label is not None
        if (self.kind is QuestionKind.WEIGHTED) != has_anchors:
            raise ValueError("only weighted choices require two scale anchors")
        if self.scale_low_label == self.scale_high_label and has_anchors:
            raise ValueError("scale anchors must differ")


# Separate variants make the decoder's JSON schema express interaction-specific
# constraints; the shared base remains useful after parsing for later safety gates.
class GeneratedChoiceQuestion(CandidateQuestion):
    """Generated single, multiple, or partner-guess interaction."""

    kind: Literal[QuestionKind.SINGLE, QuestionKind.MULTIPLE, QuestionKind.PARTNER_GUESS]
    options: list[str] = Field(min_length=2, max_length=6)
    option_icons: list[IconKey] = Field(min_length=2, max_length=6)
    scale_low_label: None = None
    scale_high_label: None = None
    concept_family: str = Field(pattern=r"^[a-z0-9-]{3,80}$")
    concept_summary: str = Field(min_length=8, max_length=180)


class GeneratedWeightedQuestion(CandidateQuestion):
    """Generated choices that are each rated independently from one to five."""

    kind: Literal[QuestionKind.WEIGHTED]
    options: list[str] = Field(min_length=2, max_length=5)
    option_icons: list[IconKey] = Field(min_length=2, max_length=5)
    scale_low_label: str = Field(min_length=1, max_length=32)
    scale_high_label: str = Field(min_length=1, max_length=32)
    concept_family: str = Field(pattern=r"^[a-z0-9-]{3,80}$")
    concept_summary: str = Field(min_length=8, max_length=180)


class GeneratedOpenQuestion(CandidateQuestion):
    """Generated free-text interaction."""

    kind: Literal[QuestionKind.FREE_TEXT]
    options: list[str] = Field(max_length=0)
    option_icons: list[IconKey] = Field(max_length=0)
    scale_low_label: None = None
    scale_high_label: None = None
    concept_family: str = Field(pattern=r"^[a-z0-9-]{3,80}$")
    concept_summary: str = Field(min_length=8, max_length=180)


GeneratedCandidate = Annotated[
    GeneratedChoiceQuestion | GeneratedWeightedQuestion | GeneratedOpenQuestion,
    Field(discriminator="kind"),
]


class GeneratedBatch(BaseModel):
    """One strict calendar-date response from the local model."""

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["3"]
    date: date
    questions: list[GeneratedCandidate] = Field(min_length=10, max_length=10)


class PublishedPool(BaseModel):
    """Validated publishable questions and reproducibility metadata."""

    date: date
    general: list[CandidateQuestion] = Field(min_length=5, max_length=5)
    intimacy_alternatives: list[CandidateQuestion]
    prompt_version: str
    model: str
    model_manifest_digest: str
    fallback_reason: str | None = None


class LearningQuestionSignal(BaseModel):
    """K-anonymous product signal supplied to the local learning pass."""

    model_config = ConfigDict(extra="forbid")

    concept_family: str = Field(min_length=3, max_length=80)
    category: Category
    rating_count: int = Field(ge=5)
    average_stars: float = Field(ge=1, le=5)
    tag_counts: dict[str, int]
    reviews: list[str] = Field(default_factory=list, max_length=20)


class LearningPolicy(BaseModel):
    """Strict, bounded guidance learned from consented aggregate feedback."""

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["1"]
    avoid_concepts: list[str] = Field(max_length=20)
    prefer_categories: dict[Category, float]
    guidance: list[str] = Field(max_length=12)
    review_themes: list[str] = Field(max_length=12)

    @model_validator(mode="after")
    def bounded_weights(self) -> "LearningPolicy":
        """Reject policy weights that could overwhelm core safety instructions."""

        if any(value < 0.5 or value > 1.5 for value in self.prefer_categories.values()):
            raise ValueError("category policy weights must remain between 0.5 and 1.5")
        return self
