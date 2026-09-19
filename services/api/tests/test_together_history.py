"""Shared-home day boundary regressions for together-time history."""

from datetime import date

from little_orbit_api.together_history_service import day_bounds


def test_spring_dst_day_has_twenty_three_hours() -> None:
    start, end = day_bounds(date(2026, 3, 8), "America/Los_Angeles")

    assert int((end - start).total_seconds()) == 23 * 3_600


def test_fall_dst_day_has_twenty_five_hours() -> None:
    start, end = day_bounds(date(2026, 11, 1), "America/Los_Angeles")

    assert int((end - start).total_seconds()) == 25 * 3_600


def test_invalid_legacy_timezone_falls_back_to_utc() -> None:
    start, end = day_bounds(date(2026, 6, 1), "Not/A-Timezone")

    assert int((end - start).total_seconds()) == 24 * 3_600
