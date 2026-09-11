"""Unicode code-point note operations and deterministic transformation rules."""

from dataclasses import dataclass
from typing import Literal


@dataclass(frozen=True)
class Insert:
    """Insert text before a Unicode code-point position."""

    position: int
    text: str
    kind: Literal["insert"] = "insert"


@dataclass(frozen=True)
class Delete:
    """Delete a count of Unicode code points at a position."""

    position: int
    length: int
    kind: Literal["delete"] = "delete"


Edit = Insert | Delete


class InvalidEdit(ValueError):
    """Raised when an operation cannot apply to the current body."""


def apply_edit(body: str, edit: Edit) -> str:
    """Apply an edit after validating its code-point range."""

    if edit.position < 0 or edit.position > len(body):
        raise InvalidEdit("position is outside the note")
    if isinstance(edit, Insert):
        if not edit.text:
            raise InvalidEdit("insert text must not be empty")
        return body[: edit.position] + edit.text + body[edit.position :]
    if edit.length <= 0 or edit.position + edit.length > len(body):
        raise InvalidEdit("delete range is outside the note")
    return body[: edit.position] + body[edit.position + edit.length :]


def transform(incoming: Edit, applied: Edit, incoming_wins_tie: bool) -> Edit:
    """Transform an incoming edit against one already-applied concurrent edit.

    Operation IDs determine `incoming_wins_tie` so every participant resolves
    inserts at the same position in the same order.
    """

    if isinstance(applied, Insert):
        return _against_insert(incoming, applied, incoming_wins_tie)
    return _against_delete(incoming, applied)


def _against_insert(incoming: Edit, applied: Insert, incoming_wins_tie: bool) -> Edit:
    shift = len(applied.text)
    if isinstance(incoming, Insert):
        should_shift = incoming.position > applied.position or (
            incoming.position == applied.position and not incoming_wins_tie
        )
        return Insert(
            incoming.position + shift if should_shift else incoming.position, incoming.text
        )
    if incoming.position >= applied.position:
        return Delete(incoming.position + shift, incoming.length)
    if incoming.position + incoming.length <= applied.position:
        return incoming
    return Delete(incoming.position, incoming.length + shift)


def _against_delete(incoming: Edit, applied: Delete) -> Edit:
    start = applied.position
    end = start + applied.length
    if isinstance(incoming, Insert):
        if incoming.position <= start:
            return incoming
        return Insert(max(start, incoming.position - applied.length), incoming.text)
    incoming_end = incoming.position + incoming.length
    new_start = incoming.position - min(applied.length, max(0, incoming.position - start))
    overlap = max(0, min(incoming_end, end) - max(incoming.position, start))
    return Delete(new_start, max(0, incoming.length - overlap))
