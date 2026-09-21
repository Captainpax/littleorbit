"""Strict Little Orbit 1.2 quiz and private-feedback contracts."""

from datetime import date, datetime
from typing import Annotated, Literal
from uuid import UUID

from pydantic import Field, model_validator

from .quiz_v2_schemas import QuizHistoryItem, QuizQuestionV2
from .schema_base import StrictModel, StrictText

FeedbackTag = Literal[
    "fun",
    "meaningful",
    "surprising",
    "clear",
    "sparked_conversation",
    "repeated",
    "too_shallow",
    "too_intense",
    "awkward",
    "irrelevant",
    "unclear",
]
ReviewStatus = Literal["accepted", "rejected", "consent_required", "none"]


class QuizFeedbackMutation(StrictModel):
    """Idempotent create or edit request for one private question rating."""

    operation_id: UUID
    expected_revision: int = Field(ge=0)
    stars: int = Field(ge=1, le=5)
    tags: list[FeedbackTag] = Field(default_factory=list, max_length=3)
    review: Annotated[StrictText, Field(min_length=1, max_length=300)] | None = None
    review_consent: bool = False

    @model_validator(mode="after")
    def unique_tags(self) -> "QuizFeedbackMutation":
        """Prevent one tag from carrying accidental extra weight."""

        if len(set(self.tags)) != len(self.tags):
            raise ValueError("feedback tags must be unique")
        return self


class QuizFeedbackDelete(StrictModel):
    """Retry-safe optimistic removal of attributable feedback."""

    operation_id: UUID
    expected_revision: int = Field(ge=1)


class QuizFeedbackView(StrictModel):
    """Only the authenticated person's own feedback."""

    revision: int = Field(ge=1)
    stars: int = Field(ge=1, le=5)
    tags: list[FeedbackTag] = Field(max_length=3)
    review: str | None
    review_status: ReviewStatus
    editable_until: datetime
    updated_at: datetime


class QuizFeedbackDeleteResult(StrictModel):
    """Stable replay result for a successful delete."""

    deleted: Literal[True] = True
    revision: Literal[0] = 0


class QuizQuestionV3(QuizQuestionV2):
    """One v2-compatible question extended with private feedback state."""

    feedback_eligible: bool = False
    feedback_editable_until: datetime | None = None
    my_feedback: QuizFeedbackView | None = None


class QuizDayV3(StrictModel):
    """A v2-shaped day whose question list carries feedback state."""

    quiz_date: date
    status: Literal["not_started", "in_progress", "waiting", "revealed", "expired"]
    revision: int = Field(ge=0)
    my_finished: bool
    partner_finished: bool
    revealed: bool
    editable: bool
    questions: list[QuizQuestionV3] = Field(min_length=5, max_length=5)


class QuizHistoryV3(QuizHistoryItem):
    """History navigation with only the caller's private rating count."""

    rated_count: int = Field(ge=0, le=5)


class QuizFeedbackAggregateView(StrictModel):
    """Thresholded, identity-free Big Orbit analytics for one question."""

    question_id: UUID
    prompt: str
    category: str
    intimacy: bool
    rating_count: int = Field(ge=5)
    average_stars: float = Field(ge=1, le=5)
    tag_counts: dict[FeedbackTag, int]
    sanitized_reviews: list[str]
    week_start: date
