"""Private-byte expiry and orphan cleanup for note attachments."""

import asyncio
from datetime import datetime, timedelta
from pathlib import Path

from sqlalchemy import and_, delete, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from .attachment_models import NoteAttachment
from .attachment_storage import available_path, processing_path, staging_path
from .models import Note


async def prepare_attachment_cleanup(
    session: AsyncSession, now: datetime
) -> list[str]:
    """Delete expired metadata after capturing every related private storage key."""

    expired_notes = select(Note.id).where(
        Note.purge_after.is_not(None), Note.purge_after <= now
    )
    stale_upload = (
        NoteAttachment.status == "uploading",
        NoteAttachment.updated_at <= now - timedelta(hours=24),
    )
    old_rejection = (
        NoteAttachment.status == "rejected",
        NoteAttachment.updated_at <= now - timedelta(days=7),
    )
    keys = list(
        await session.scalars(
            select(NoteAttachment.storage_key).where(
                or_(
                    NoteAttachment.note_id.in_(expired_notes),
                    and_(*stale_upload),
                    and_(*old_rejection),
                )
            )
        )
    )
    await session.execute(delete(NoteAttachment).where(*stale_upload))
    await session.execute(delete(NoteAttachment).where(*old_rejection))
    return keys


async def delete_attachment_files(root: Path, storage_keys: list[str]) -> None:
    """Remove unpublished, processing, and sanitized bytes for deleted metadata."""

    for storage_key in set(storage_keys):
        await asyncio.gather(
            asyncio.to_thread(staging_path(root, storage_key).unlink, missing_ok=True),
            asyncio.to_thread(processing_path(root, storage_key).unlink, missing_ok=True),
            asyncio.to_thread(available_path(root, storage_key).unlink, missing_ok=True),
        )


async def delete_orphan_files(
    root: Path, known_keys: set[str], now: datetime
) -> int:
    """Remove hour-old files that have no corresponding authorized metadata."""

    return await asyncio.to_thread(_delete_orphans_sync, root, known_keys, now.timestamp())


def _delete_orphans_sync(root: Path, known_keys: set[str], now_timestamp: float) -> int:
    removed = 0
    cutoff = now_timestamp - 3600
    locations = (
        (root / "staging", ".upload"),
        (root / "processing", ".work"),
        (root / "available", ""),
    )
    for directory, suffix in locations:
        if not directory.is_dir():
            continue
        for candidate in directory.iterdir():
            key = candidate.name[: -len(suffix)] if suffix else candidate.name
            if candidate.is_file() and key not in known_keys and candidate.stat().st_mtime <= cutoff:
                candidate.unlink(missing_ok=True)
                removed += 1
    return removed
