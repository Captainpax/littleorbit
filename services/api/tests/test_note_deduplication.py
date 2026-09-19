"""Safe duplicate classification regressions."""

from datetime import UTC, datetime
from uuid import uuid4

from little_orbit_api.models import Note
from little_orbit_api.note_deduplication import _Candidate, _safe_duplicates


def test_attachment_owner_wins_over_untouched_duplicate() -> None:
    canonical = _note(revision=0)
    duplicate = _note(revision=0, couple_id=canonical.couple_id)

    selected = _safe_duplicates([_Candidate(canonical, 1), _Candidate(duplicate, 0)])

    assert selected == [duplicate]


def test_single_edited_note_wins_over_untouched_duplicates() -> None:
    canonical = _note(revision=2)
    duplicate = _note(revision=0, couple_id=canonical.couple_id)

    selected = _safe_duplicates([_Candidate(canonical, 0), _Candidate(duplicate, 0)])

    assert selected == [duplicate]


def test_multiple_attachment_owners_require_manual_review() -> None:
    first = _note(revision=0)
    second = _note(revision=0, couple_id=first.couple_id)

    assert _safe_duplicates([_Candidate(first, 1), _Candidate(second, 1)]) is None


def _note(*, revision: int, couple_id=None) -> Note:
    now = datetime(2026, 9, 19, tzinfo=UTC)
    return Note(
        id=uuid4(),
        creation_operation_id=uuid4(),
        couple_id=couple_id or uuid4(),
        title="same",
        body="same body",
        revision=revision,
        metadata_revision=0,
        created_at=now,
        updated_at=now,
    )
