"""Little Orbit 1.3 quiz contracts with public theme and depth metadata."""

from datetime import date
from typing import Annotated, Literal

from pydantic import Field

from .quiz_v3_schemas import QuizHistoryV3, QuizQuestionV3
from .schema_base import StrictModel, StrictText


class QuizThemeView(StrictModel):
    """Public editorial labels for one day; no feedback or generation content."""

    weekly_title: Annotated[StrictText, Field(min_length=3, max_length=80)]
    weekly_summary: Annotated[StrictText, Field(min_length=12, max_length=240)]
    daily_title: Annotated[StrictText, Field(min_length=3, max_length=80)]
    daily_summary: Annotated[StrictText, Field(min_length=12, max_length=240)]
    observance: Annotated[StrictText, Field(min_length=3, max_length=120)] | None = None


class QuizQuestionV4(QuizQuestionV3):
    """Feedback-compatible question with its reviewed conversation role."""

    depth: Literal["light", "reflective", "deeper"] = "reflective"
    theme_role: Literal["themed", "variety"] = "variety"
    theme_tags: list[str] = Field(default_factory=list, max_length=4)


class QuizDayV4(StrictModel):
    """Stable daily quiz plus the optional 1.3 editorial theme."""

    quiz_date: date
    status: Literal["not_started", "in_progress", "waiting", "revealed", "expired"]
    revision: int = Field(ge=0)
    my_finished: bool
    partner_finished: bool
    revealed: bool
    editable: bool
    theme: QuizThemeView | None = None
    questions: list[QuizQuestionV4] = Field(min_length=5, max_length=5)


class QuizHistoryV4(QuizHistoryV3):
    """Content-free history navigation with a short daily theme label."""

    daily_theme: str | None = None
    quiz_date: date
