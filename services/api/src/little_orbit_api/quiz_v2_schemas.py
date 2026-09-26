"""Strict version-two daily quiz request and response models."""

from datetime import date
from typing import Annotated, Literal
from uuid import UUID

from pydantic import Field, model_validator

from .schema_base import StrictModel, StrictText


class QuizOptionV2(StrictModel):
    """Stable option identity and audited visual hint."""

    id: str = Field(pattern=r"^o[1-6]$")
    label: Annotated[StrictText, Field(min_length=1, max_length=64)]
    icon_key: Literal[
        "heart", "chat", "home", "meal", "movie", "music", "outdoors", "play",
        "rest", "star", "travel", "surprise"
    ]


class SingleChoiceAnswer(StrictModel):
    """One selected option."""

    kind: Literal["single_choice"]
    selected_option_id: str = Field(pattern=r"^o[1-6]$")


class MultipleChoiceAnswer(StrictModel):
    """One or more distinct selected options."""

    kind: Literal["multiple_choice"]
    selected_option_ids: list[str] = Field(min_length=1, max_length=6)

    @model_validator(mode="after")
    def unique_options(self) -> "MultipleChoiceAnswer":
        """Reject duplicated choices before persistence."""

        if len(set(self.selected_option_ids)) != len(self.selected_option_ids):
            raise ValueError("selected options must be unique")
        return self


class FreeTextAnswer(StrictModel):
    """Bounded plain-text response."""

    kind: Literal["free_text"]
    text: Annotated[StrictText, Field(min_length=1, max_length=2000)]


class PartnerGuessAnswer(StrictModel):
    """A person's own selection and their private guess for their partner."""

    kind: Literal["partner_guess"]
    self_option_id: str = Field(pattern=r"^o[1-6]$")
    guess_option_id: str = Field(pattern=r"^o[1-6]$")


class WeightedChoiceAnswer(StrictModel):
    """One rating for every option in a weighted-choice question."""

    kind: Literal["weighted_choice"]
    ratings: dict[str, int] = Field(min_length=2, max_length=5)

    @model_validator(mode="after")
    def valid_ratings(self) -> "WeightedChoiceAnswer":
        """Require option-shaped keys and bounded one-to-five values."""

        if any(not key.startswith("o") or value not in range(1, 6) for key, value in self.ratings.items()):
            raise ValueError("ratings must map option IDs to values from 1 through 5")
        return self


class LegacyWeightedAnswer(StrictModel):
    """Read-compatible one-to-five rating for a pre-RC5 question."""

    kind: Literal["weighted_scale"]
    rating: int = Field(ge=1, le=5)


QuizAnswerV2 = Annotated[
    SingleChoiceAnswer
    | MultipleChoiceAnswer
    | FreeTextAnswer
    | PartnerGuessAnswer
    | WeightedChoiceAnswer
    | LegacyWeightedAnswer,
    Field(discriminator="kind"),
]


class QuizDraftMutation(StrictModel):
    """Retry-safe optimistic private-draft mutation."""

    operation_id: UUID
    expected_revision: int = Field(ge=0)
    answer: QuizAnswerV2


class QuizDayMutation(StrictModel):
    """Retry-safe finish or reopen request for one daily snapshot."""

    operation_id: UUID
    expected_day_revision: int = Field(ge=0)


class QuizQuestionV2(StrictModel):
    """One ordered interaction with partner content gated by daily reveal."""

    id: UUID
    position: int = Field(ge=1, le=5)
    interaction_version: int
    kind: str
    prompt: str
    category: str
    intimacy: bool
    options: list[QuizOptionV2]
    scale_low_label: str | None = None
    scale_high_label: str | None = None
    my_answer: dict[str, object] | None = None
    my_answer_revision: int = Field(ge=0)
    partner_answer: dict[str, object] | None = None


class QuizDayResponse(StrictModel):
    """Stable UTC quiz day with privacy-safe progress and reveal state."""

    quiz_date: date
    status: Literal["not_started", "in_progress", "waiting", "revealed", "expired"]
    revision: int = Field(ge=0)
    my_finished: bool
    partner_finished: bool
    revealed: bool
    editable: bool
    questions: list[QuizQuestionV2] = Field(min_length=5, max_length=5)


class QuizHistoryItem(StrictModel):
    """Content-free navigation state for one of the previous thirty UTC days."""

    quiz_date: date
    status: Literal["not_started", "in_progress", "waiting", "revealed", "expired"]
    answered_count: int = Field(ge=0, le=5)
    custom_count: int = Field(ge=0, le=5)


class QuizStatusResponse(StrictModel):
    """Small response used by delayed private Android polling."""

    quiz_date: date
    state_version: int = Field(ge=0)
    my_finished: bool
    partner_finished: bool
    revealed: bool


class CustomQuestionV2Request(StrictModel):
    """A surprise-capable custom prompt assigned by the server's UTC queue."""

    kind: Literal[
        "single_choice", "multiple_choice", "free_text", "partner_guess", "weighted_choice"
    ]
    prompt: Annotated[StrictText, Field(min_length=12, max_length=240)]
    category: Literal[
        "everyday", "memories", "dreams", "values", "playful", "connection", "intimacy"
    ]
    intimacy: bool
    options: list[QuizOptionV2] = Field(max_length=6)
    scale_low_label: Annotated[StrictText, Field(min_length=1, max_length=32)] | None = None
    scale_high_label: Annotated[StrictText, Field(min_length=1, max_length=32)] | None = None
    surprise: bool = True

    @model_validator(mode="after")
    def validate_interaction(self) -> "CustomQuestionV2Request":
        """Apply the same shape invariants as generated v2 content."""

        needs_options = self.kind != "free_text"
        upper = 5 if self.kind == "weighted_choice" else 6
        if needs_options and not 2 <= len(self.options) <= upper:
            raise ValueError("this interaction requires 2-6 options")
        if not needs_options and self.options:
            raise ValueError("free-text questions cannot contain options")
        expected_ids = [f"o{index}" for index in range(1, len(self.options) + 1)]
        if [option.id for option in self.options] != expected_ids:
            raise ValueError("option IDs must be consecutive starting with o1")
        anchors = self.scale_low_label is not None and self.scale_high_label is not None
        if (self.kind == "weighted_choice") != anchors:
            raise ValueError("only weighted choices require scale labels")
        if self.intimacy != (self.category == "intimacy"):
            raise ValueError("intimacy flag must match the intimacy category")
        return self


class CustomQuestionV2Response(StrictModel):
    """Creator-visible pending custom question metadata."""

    id: UUID
    publish_date: date
    custom_slot: int = Field(ge=1, le=5)
    prompt: str
    kind: str
    category: str
    surprise: bool


class CustomQueueResponse(StrictModel):
    """Creator details plus a content-free count of partner surprises."""

    mine: list[CustomQuestionV2Response]
    shared: list[CustomQuestionV2Response]
    partner_surprise_count: int = Field(ge=0)


class QuestionReportV2Request(StrictModel):
    """Structured reason for hiding one daily question."""

    reason_code: Literal["uncomfortable", "unclear", "repeated", "irrelevant", "unsafe", "other"]
    details: Annotated[StrictText, Field(max_length=300)] = ""
