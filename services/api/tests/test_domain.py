"""Pure domain behavior tests for notes and location estimates."""

import pytest
from pydantic import ValidationError

from little_orbit_api.domain.location import Point, decide_proximity
from little_orbit_api.domain.notes import Delete, Insert, InvalidEdit, apply_edit, transform
from little_orbit_api.schemas import RegistrationRequest


def test_note_offsets_count_emoji_as_one_code_point() -> None:
    assert apply_edit("A🌙B", Delete(position=1, length=1)) == "AB"
    assert apply_edit("A🌙B", Insert(position=2, text="!")) == "A🌙!B"


def test_identical_insert_positions_converge_by_tie_break() -> None:
    left = Insert(1, "A")
    right = Insert(1, "B")
    left_after_right = transform(left, right, incoming_wins_tie=True)
    right_after_left = transform(right, left, incoming_wins_tie=False)
    assert apply_edit(apply_edit("xy", right), left_after_right) == "xABy"
    assert apply_edit(apply_edit("xy", left), right_after_left) == "xABy"


def test_out_of_bounds_note_edit_fails_without_mutation() -> None:
    with pytest.raises(InvalidEdit):
        apply_edit("small", Delete(4, 2))


def test_location_requires_accuracy_bound_to_fit_threshold() -> None:
    same_place_poor_accuracy = decide_proximity(Point(45, -122, 80), Point(45, -122, 80))
    same_place_good_accuracy = decide_proximity(Point(45, -122, 5), Point(45, -122, 5))
    assert same_place_poor_accuracy.uncertain
    assert not same_place_poor_accuracy.together
    assert same_place_good_accuracy.together


def test_registration_honeypot_reaches_neutral_route_logic_but_stays_bounded() -> None:
    accepted = RegistrationRequest(
        email="bot@example.com",
        password="long-enough-password",
        display_name="Bot",
        is_adult=True,
        accepted_terms_version="2026-09-10",
        website="filled-by-bot",
    )
    assert accepted.website == "filled-by-bot"
    with pytest.raises(ValidationError):
        RegistrationRequest(
            email="bot@example.com",
            password="long-enough-password",
            display_name="Bot",
            is_adult=True,
            accepted_terms_version="2026-09-10",
            website="x" * 201,
        )
