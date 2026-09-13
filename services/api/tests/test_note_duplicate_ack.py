"""Regression tests for retry-safe live-note acknowledgements."""

from types import SimpleNamespace
from uuid import uuid4

from little_orbit_api.note_edit_service import NoteEditMessage, _duplicate_ack


def test_duplicate_ack_returns_current_body_and_revision() -> None:
    """A retried operation cannot rewind observers to its historical revision."""

    operation_id = uuid4()
    existing = SimpleNamespace(base_revision=2, resulting_revision=3)
    note = SimpleNamespace(body="current body", revision=8)
    message = NoteEditMessage(
        operation_id=operation_id,
        base_revision=2,
        kind="insert",
        position=0,
        text="old",
    )

    result = _duplicate_ack(existing, note, message)  # type: ignore[arg-type]

    assert result["duplicate"] is True
    assert result["revision"] == 8
    assert result["body"] == "current body"
