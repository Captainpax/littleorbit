"""Focused tests for RC10 Smooch rules that must stay deterministic."""

from datetime import UTC, date, datetime, timedelta
from uuid import UUID

from little_orbit_api.smooch_service import (
    EMOJIS,
    PHRASE_KEYS,
    choose_phrase,
    retry_after_seconds,
    week_bounds_utc,
    week_start,
)


def test_fixed_vocabulary_has_exactly_nine_distinct_choices() -> None:
    assert len(EMOJIS) == 9
    assert len(set(EMOJIS)) == 9


def test_phrase_choice_is_stable_for_idempotent_retry() -> None:
    operation = UUID("0f52ee89-277f-4fd0-8e29-325d6fc86611")
    assert choose_phrase(operation) == choose_phrase(operation)
    assert choose_phrase(operation) in PHRASE_KEYS


def test_rolling_hour_opens_slot_after_oldest_send() -> None:
    now = datetime(2026, 9, 12, 20, 0, tzinfo=UTC)
    sent = [now - timedelta(minutes=value) for value in (59, 40, 30, 20, 10)]
    assert retry_after_seconds(sent, now) == 61
    assert retry_after_seconds(sent[1:], now) == 0


def test_week_bounds_follow_local_monday_across_dst() -> None:
    instant = datetime(2026, 10, 28, 8, tzinfo=UTC)
    start = week_start(instant, "America/Los_Angeles")
    lower, upper = week_bounds_utc(start, "America/Los_Angeles")
    assert start == date(2026, 10, 26)
    assert lower < instant < upper
    assert upper - lower == timedelta(days=7, hours=1)
