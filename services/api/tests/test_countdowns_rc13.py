"""RC13 calendar timing and private-reminder contract tests."""

from datetime import UTC, date, datetime
from uuid import uuid4

import pytest
from fastapi import HTTPException
from pydantic import ValidationError

from little_orbit_api.routes.countdowns import _validated_time
from little_orbit_api.schemas import CountdownMutation, CountdownReminderUpdate


def mutation(**changes: object) -> CountdownMutation:
    payload: dict[str, object] = {
        "operation_id": uuid4(),
        "title": "Cabin weekend",
        "occurs_at": datetime(2026, 11, 1, tzinfo=UTC),
        "timezone": "America/Los_Angeles",
        "notes": "",
    }
    payload.update(changes)
    return CountdownMutation.model_validate(payload)


def test_legacy_timed_mutation_keeps_additive_defaults() -> None:
    value = mutation()

    assert value.timing_kind == "timed"
    assert value.occurs_on is None


def test_all_day_uses_local_midnight_as_compatibility_anchor() -> None:
    value = mutation(timing_kind="all_day", occurs_on=date(2026, 11, 1))

    assert _validated_time(value) == datetime(2026, 11, 1, 7, tzinfo=UTC)


def test_timed_event_rejects_an_all_day_calendar_date() -> None:
    with pytest.raises(HTTPException) as failure:
        _validated_time(mutation(occurs_on=date(2026, 11, 1)))

    assert failure.value.status_code == 422


def test_reminder_contract_is_bounded_to_audited_offsets() -> None:
    value = CountdownReminderUpdate(offsets_minutes=[0, 60, 1440, 10080])
    assert value.offsets_minutes == [0, 60, 1440, 10080]

    with pytest.raises(ValidationError):
        CountdownReminderUpdate(offsets_minutes=[30])  # type: ignore[list-item]
