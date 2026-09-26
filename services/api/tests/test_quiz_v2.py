"""RC5 quiz interaction, validation, and reveal-boundary tests."""

from uuid import uuid4

import pytest
from fastapi import HTTPException
from pydantic import ValidationError

from little_orbit_api.models import Question
from little_orbit_api.quiz_v2_service import validate_answer
from little_orbit_api.schemas import (
    CustomQuestionV2Request,
    PartnerGuessAnswer,
    QuizDraftMutation,
    QuizOptionV2,
    SingleChoiceAnswer,
    WeightedChoiceAnswer,
)


def question(kind: str, option_count: int = 3) -> Question:
    """Build a persistence-free question for domain validation."""

    return Question(kind=kind, options=[f"Choice {index}" for index in range(option_count)])


def test_partner_guess_keeps_self_and_guess_as_separate_choices() -> None:
    """Partner guessing carries both selections without implying a score."""

    answer = PartnerGuessAnswer(
        kind="partner_guess", self_option_id="o1", guess_option_id="o3"
    )
    assert validate_answer(question("partner_guess"), answer) == {
        "kind": "partner_guess",
        "self_option_id": "o1",
        "guess_option_id": "o3",
    }


def test_weighted_choice_requires_every_option_once() -> None:
    """A partial rating map cannot be persisted as a completed interaction."""

    answer = WeightedChoiceAnswer(kind="weighted_choice", ratings={"o1": 4, "o2": 2})
    with pytest.raises(HTTPException, match="Every option"):
        validate_answer(question("weighted_choice", 3), answer)


def test_answer_kind_must_match_stable_question_snapshot() -> None:
    """A client cannot change an interaction by posting a different answer shape."""

    answer = SingleChoiceAnswer(kind="single_choice", selected_option_id="o1")
    with pytest.raises(HTTPException, match="kind does not match"):
        validate_answer(question("partner_guess"), answer)


def test_duplicate_multiple_choices_fail_before_service_code() -> None:
    """Repeated option IDs are rejected by the versioned input contract."""

    with pytest.raises(ValidationError, match="selected options must be unique"):
        QuizDraftMutation.model_validate(
            {
                "operation_id": str(uuid4()),
                "expected_revision": 0,
                "answer": {
                    "kind": "multiple_choice",
                    "selected_option_ids": ["o1", "o1"],
                },
            }
        )


def test_custom_weighted_question_has_bounded_options_and_anchors() -> None:
    """Guided custom content uses the same weighted interaction as generated content."""

    options = [
        QuizOptionV2(id=f"o{index}", label=f"Plan {index}", icon_key="heart")
        for index in range(1, 4)
    ]
    created = CustomQuestionV2Request(
        kind="weighted_choice",
        prompt="How much would each plan help us reconnect this weekend?",
        category="connection",
        intimacy=False,
        options=options,
        scale_low_label="Not much",
        scale_high_label="Very much",
    )
    assert len(created.options) == 3


def test_custom_intimacy_tag_cannot_disagree_with_category() -> None:
    """The mutual-consent gate cannot be bypassed through mismatched metadata."""

    with pytest.raises(ValidationError, match="intimacy flag"):
        CustomQuestionV2Request(
            kind="free_text",
            prompt="What kind of affection would feel most caring tonight?",
            category="intimacy",
            intimacy=False,
            options=[],
        )
