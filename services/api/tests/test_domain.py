"""Pure domain behavior tests for notes and location estimates."""

from datetime import UTC, datetime, timedelta

import pytest
from pydantic import ValidationError

from little_orbit_api.domain.location import (
    Point,
    TimedPoint,
    decide_proximity,
    estimate_nearby_minutes,
)
from little_orbit_api.domain.notes import Delete, Insert, InvalidEdit, apply_edit, transform
from little_orbit_api.schemas import CouplePreferencesRequest, RegistrationRequest
from little_orbit_api.together_time_service import relationship_days


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


def test_nearby_estimate_counts_interval_between_confident_samples() -> None:
    start = datetime(2026, 9, 12, 10, 2, 30, tzinfo=UTC)
    left = [_sample("left-a", start), _sample("left-b", start + timedelta(minutes=15))]
    right = [
        _sample("right-a", start + timedelta(seconds=20)),
        _sample("right-b", start + timedelta(minutes=15, seconds=20)),
    ]

    buckets = estimate_nearby_minutes(left, right)

    assert sum(item.duration_seconds for item in buckets) == 15 * 60
    assert len({item.bucket_start for item in buckets}) == len(buckets)


def test_nearby_estimate_breaks_on_uncertainty_and_long_gap() -> None:
    start = datetime(2026, 9, 12, 10, tzinfo=UTC)
    good = [_sample("a", start), _sample("b", start + timedelta(minutes=21))]
    poor = [
        _sample("c", start, accuracy=80),
        _sample("d", start + timedelta(minutes=21), accuracy=80),
    ]

    assert estimate_nearby_minutes(good, good) == []
    assert estimate_nearby_minutes(good, poor) == []


def test_relationship_age_uses_complete_utc_calendar_days() -> None:
    now = datetime(2026, 9, 12, 23, 59, tzinfo=UTC)
    assert relationship_days(now.date() - timedelta(days=10), now) == 10
    assert relationship_days(None, now) is None


def test_preferences_reject_direct_anniversary_mutation() -> None:
    with pytest.raises(ValidationError):
        CouplePreferencesRequest.model_validate({"anniversary_date": "2020-01-01"})


def _sample(name: str, recorded_at: datetime, accuracy: float = 5) -> TimedPoint:
    return TimedPoint(name, recorded_at, Point(45, -122, accuracy))


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
