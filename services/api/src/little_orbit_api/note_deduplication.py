"""Content-safe classification and reversible archival of exact note duplicates."""

from dataclasses import dataclass
from datetime import timedelta
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from .attachment_models import NoteAttachment
from .clock import SystemClock
from .models import Couple, Note


@dataclass(frozen=True)
class DuplicateReport:
    """Content-free result suitable for operator logs."""

    groups: int
    safe_to_archive: int
    ambiguous_groups: int
    archived: int


@dataclass(frozen=True)
class _Candidate:
    note: Note
    attachment_count: int


async def classify_and_archive_duplicates(
    session: AsyncSession, *, apply: bool
) -> DuplicateReport:
    """Archive only exact, untouched duplicates while retaining one canonical note."""

    candidates = await _candidates(session)
    groups = _groups(candidates)
    safe, ambiguous = _classify(groups)
    archived = await _archive(session, safe) if apply and safe else 0
    return DuplicateReport(len(groups), len(safe), ambiguous, archived)


def _classify(groups: list[list[_Candidate]]) -> tuple[list[Note], int]:
    safe: list[Note] = []
    ambiguous = 0
    for values in groups:
        selected = _safe_duplicates(values)
        if selected is None:
            ambiguous += 1
        else:
            safe.extend(selected)
    return safe, ambiguous


async def _archive(session: AsyncSession, safe: list[Note]) -> int:
    couple_ids = sorted({note.couple_id for note in safe}, key=str)
    await session.execute(
        select(Couple).where(Couple.id.in_(couple_ids)).order_by(Couple.id).with_for_update()
    )
    archived = 0
    now = SystemClock().now()
    for note in safe:
        locked = await session.scalar(
            select(Note).where(Note.id == note.id).with_for_update()
        )
        attachment_count = await session.scalar(
            select(func.count(NoteAttachment.id)).where(
                NoteAttachment.note_id == note.id,
                NoteAttachment.deleted_at.is_(None),
            )
        )
        if not _still_safe(locked, int(attachment_count or 0)):
            continue
        assert locked is not None
        locked.archived_at = now
        locked.purge_after = now + timedelta(days=7)
        locked.metadata_revision += 1
        locked.updated_at = now
        archived += 1
    await session.commit()
    return archived


def _still_safe(note: Note | None, attachment_count: int) -> bool:
    return bool(
        note is not None
        and note.archived_at is None
        and note.revision == 0
        and note.metadata_revision == 0
        and attachment_count == 0
    )


async def _candidates(session: AsyncSession) -> list[_Candidate]:
    rows = await session.execute(
        select(Note, func.count(NoteAttachment.id))
        .outerjoin(
            NoteAttachment,
            (NoteAttachment.note_id == Note.id) & NoteAttachment.deleted_at.is_(None),
        )
        .where(Note.archived_at.is_(None))
        .group_by(Note.id)
        .order_by(Note.couple_id, Note.created_at, Note.id)
    )
    return [_Candidate(note, int(count)) for note, count in rows.tuples().all()]


def _groups(candidates: list[_Candidate]) -> list[list[_Candidate]]:
    grouped: dict[tuple[UUID, str, str], list[_Candidate]] = {}
    for item in candidates:
        grouped.setdefault(
            (item.note.couple_id, item.note.title, item.note.body), []
        ).append(item)
    return [items for items in grouped.values() if len(items) > 1]


def _safe_duplicates(items: list[_Candidate]) -> list[Note] | None:
    attachment_owners = [item for item in items if item.attachment_count > 0]
    edited = [
        item for item in items
        if item.note.revision > 0 or item.note.metadata_revision > 0
    ]
    if len(attachment_owners) > 1 or len(edited) > 1:
        return None
    canonical = attachment_owners[0] if attachment_owners else (
        edited[0] if edited else items[0]
    )
    safe = [
        item.note for item in items
        if item.note.id != canonical.note.id
        and item.note.revision == 0
        and item.note.metadata_revision == 0
        and item.attachment_count == 0
    ]
    return safe if len(safe) == len(items) - 1 else None
