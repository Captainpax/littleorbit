"""Fail-closed malware scanning and metadata removal for note attachments."""

import asyncio
import logging
import os
import socket
import struct
from collections.abc import Callable
from datetime import datetime, timedelta
from pathlib import Path
from uuid import UUID

from sqlalchemy import and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql.elements import ColumnElement

from . import models as _models  # noqa: F401  # Register worker FK targets.
from .activity_service import record_activity
from .attachment_media_errors import AttachmentRejected, ScanUnavailable
from .attachment_models import AttachmentJob, NoteAttachment
from .attachment_quota import adjust_storage
from .attachment_sanitizers import sanitize_file
from .attachment_storage import (
    COUPLE_QUOTA_BYTES,
    MAX_FILE_BYTES,
    AttachmentPolicyError,
    available_path,
    processing_path,
    sha256_file,
    staging_path,
)
from .clock import SystemClock
from .config import Settings, get_settings
from .database import SessionFactory
from .models import Couple

LOGGER = logging.getLogger(__name__)
MAX_JOB_ATTEMPTS = 8
JOB_LEASE_MINUTES = 10
WORKER_ID = f"{socket.gethostname()}:{os.getpid()}"


def clamav_scan(path: Path, host: str, port: int) -> bool:
    """Stream one private file to clamd and return whether it is clean."""

    try:
        with socket.create_connection((host, port), timeout=15) as connection:
            connection.settimeout(90)
            connection.sendall(b"zINSTREAM\0")
            with path.open("rb") as source:
                for chunk in iter(lambda: source.read(1024 * 1024), b""):
                    connection.sendall(struct.pack(">I", len(chunk)))
                    connection.sendall(chunk)
            connection.sendall(struct.pack(">I", 0))
            response = _read_clamav_response(connection)
    except OSError as error:
        raise ScanUnavailable("clamav_unavailable") from error
    if response.endswith("OK"):
        return True
    if "FOUND" in response:
        return False
    raise ScanUnavailable("clamav_invalid_response")


def _read_clamav_response(connection: socket.socket) -> str:
    chunks: list[bytes] = []
    while True:
        chunk = connection.recv(4096)
        if not chunk:
            break
        chunks.append(chunk)
        if b"\0" in chunk or b"\n" in chunk:
            break
    return b"".join(chunks).rstrip(b"\0\n").decode("utf-8", "replace")


async def scan_pending_once(
    settings: Settings | None = None,
    scanner: Callable[[Path, str, int], bool] = clamav_scan,
) -> bool:
    """Claim and process one ready attachment without exposing unscanned bytes."""

    effective = settings or get_settings()
    attachment_id = await _claim_ready()
    if attachment_id is None:
        return False
    try:
        await _process(attachment_id, effective, scanner)
    except AttachmentRejected as error:
        LOGGER.info("attachment rejected: %s", error)
        await _reject(attachment_id, effective, str(error)[:40])
    except ScanUnavailable as error:
        LOGGER.warning("attachment scan deferred: %s", error)
        await _retry_or_reject(attachment_id, effective, str(error)[:40])
    except Exception:
        LOGGER.exception("attachment processing failed")
        await _retry_or_reject(attachment_id, effective, "processing_failed")
    return True


async def _claim_ready() -> UUID | None:
    now = SystemClock().now()
    async with SessionFactory() as session:
        job = await session.scalar(
            select(AttachmentJob)
            .join(NoteAttachment, NoteAttachment.id == AttachmentJob.attachment_id)
            .where(
                _job_is_ready(now),
                AttachmentJob.attempts < MAX_JOB_ATTEMPTS,
                NoteAttachment.deleted_at.is_(None),
                NoteAttachment.status.in_(("pending_scan", "scanning")),
            )
            .order_by(AttachmentJob.next_attempt_at, AttachmentJob.created_at)
            .with_for_update(skip_locked=True)
        )
        if job is None:
            return None
        item = await session.get(NoteAttachment, job.attachment_id, with_for_update=True)
        if item is None:
            return None
        item.status = "scanning"
        item.updated_at = now
        job.status = "leased"
        job.attempts += 1
        job.lease_expires_at = now + timedelta(minutes=JOB_LEASE_MINUTES)
        job.leased_by = WORKER_ID
        job.updated_at = now
        await session.commit()
        return item.id


def _job_is_ready(now: datetime) -> ColumnElement[bool]:
    return or_(
        and_(AttachmentJob.status == "pending", AttachmentJob.next_attempt_at <= now),
        and_(AttachmentJob.status == "leased", AttachmentJob.lease_expires_at <= now),
    )


async def _process(
    attachment_id: UUID,
    settings: Settings,
    scanner: Callable[[Path, str, int], bool],
) -> None:
    async with SessionFactory() as session:
        item = await session.get(NoteAttachment, attachment_id)
        if item is None or item.status != "scanning":
            return
        root = settings.attachment_storage_dir
        source = staging_path(root, item.storage_key)
        target = available_path(root, item.storage_key)
        work = processing_path(root, item.storage_key)
        media_type, expected_hash = item.media_type, item.sha256
    actual_hash = await asyncio.to_thread(sha256_file, source) if source.is_file() else None
    if actual_hash != expected_hash:
        raise AttachmentRejected("upload_bytes_missing_or_changed")
    clean = await asyncio.to_thread(scanner, source, settings.clamav_host, settings.clamav_port)
    if not clean:
        raise AttachmentRejected("malware_detected")
    sanitized_hash, final_size = await _publish(source, work, target, media_type)
    if not await _mark_available(attachment_id, sanitized_hash, final_size):
        raise AttachmentRejected("quota_exceeded_after_sanitization")
    await asyncio.to_thread(source.unlink, missing_ok=True)


async def _publish(
    source: Path, work: Path, target: Path, media_type: str
) -> tuple[str, int]:
    work.parent.mkdir(parents=True, exist_ok=True)
    target.parent.mkdir(parents=True, exist_ok=True)
    await asyncio.to_thread(work.unlink, missing_ok=True)
    try:
        await asyncio.to_thread(sanitize_file, source, work, media_type)
        final_size = work.stat().st_size
        if final_size > MAX_FILE_BYTES:
            raise AttachmentRejected("sanitized_file_too_large")
        digest = await asyncio.to_thread(sha256_file, work)
        await asyncio.to_thread(work.replace, target)
        return digest, final_size
    finally:
        await asyncio.to_thread(work.unlink, missing_ok=True)


async def _mark_available(
    attachment_id: UUID, sanitized_hash: str, final_size: int
) -> bool:
    async with SessionFactory() as lookup:
        couple_id = await lookup.scalar(
            select(NoteAttachment.couple_id).where(NoteAttachment.id == attachment_id)
        )
    if couple_id is None:
        return False
    async with SessionFactory() as session:
        couple = await session.get(Couple, couple_id, with_for_update=True)
        if couple is None:
            return False
        item = await session.get(NoteAttachment, attachment_id, with_for_update=True)
        if item is None or item.status != "scanning":
            return False
        if await _couple_reserved_except(session, couple_id, attachment_id) + final_size > COUPLE_QUOTA_BYTES:
            return False
        try:
            await adjust_storage(session, final_size - item.size_bytes)
        except AttachmentPolicyError:
            return False
        now = SystemClock().now()
        _complete_item(item, sanitized_hash, final_size, now)
        job = await session.get(AttachmentJob, attachment_id, with_for_update=True)
        if job is not None:
            _complete_job(job, now)
        if couple.ended_at is None:
            await record_activity(
                session,
                couple_id,
                item.uploaded_by,
                "attachment_available",
                f"attachment:available:{item.id}",
                target_type="note",
                target_id=item.note_id,
            )
        await session.commit()
        return True


async def _couple_reserved_except(
    session: AsyncSession, couple_id: UUID, attachment_id: UUID
) -> int:
    value = await session.scalar(
        select(func.coalesce(func.sum(NoteAttachment.size_bytes), 0)).where(
            NoteAttachment.couple_id == couple_id,
            NoteAttachment.deleted_at.is_(None),
            NoteAttachment.status.in_(("uploading", "pending_scan", "scanning", "available")),
            NoteAttachment.id != attachment_id,
        )
    )
    return int(value or 0)


def _complete_item(
    item: NoteAttachment, sanitized_hash: str, final_size: int, now: datetime
) -> None:
    item.status = "available"
    item.sha256 = sanitized_hash
    item.size_bytes = final_size
    item.uploaded_bytes = final_size
    item.scanned_at = now
    item.updated_at = now


def _complete_job(job: AttachmentJob, now: datetime) -> None:
    job.status = "completed"
    job.lease_expires_at = None
    job.leased_by = None
    job.last_error = None
    job.updated_at = now


async def _retry_or_reject(
    attachment_id: UUID, settings: Settings, reason: str
) -> None:
    reject = False
    async with SessionFactory() as session:
        job = await session.get(AttachmentJob, attachment_id, with_for_update=True)
        item = await session.get(NoteAttachment, attachment_id, with_for_update=True)
        if job is None or item is None:
            return
        reject = job.attempts >= MAX_JOB_ATTEMPTS
        if not reject:
            now = SystemClock().now()
            delay = min(300, 5 * (2 ** max(job.attempts - 1, 0)))
            item.status, item.updated_at = "pending_scan", now
            job.status = "pending"
            job.next_attempt_at = now + timedelta(seconds=delay)
            job.lease_expires_at = None
            job.leased_by = None
            job.last_error, job.updated_at = reason, now
            await session.commit()
    if reject:
        await _reject(attachment_id, settings, "retry_limit_exceeded")


async def _reject(attachment_id: UUID, settings: Settings, reason: str) -> None:
    async with SessionFactory() as lookup:
        couple_id = await lookup.scalar(
            select(NoteAttachment.couple_id).where(NoteAttachment.id == attachment_id)
        )
    if couple_id is None:
        return
    async with SessionFactory() as session:
        couple = await session.get(Couple, couple_id, with_for_update=True)
        if couple is None:
            return
        item = await session.get(NoteAttachment, attachment_id, with_for_update=True)
        if item is None:
            return
        if item.status in {"uploading", "pending_scan", "scanning", "available"}:
            await adjust_storage(session, -item.size_bytes)
        now = SystemClock().now()
        item.status, item.rejection_reason = "rejected", reason
        item.updated_at = now
        job = await session.get(AttachmentJob, attachment_id, with_for_update=True)
        if job is not None:
            job.status, job.last_error = "rejected", reason
            job.lease_expires_at = None
            job.leased_by = None
            job.updated_at = now
        storage_key = item.storage_key
        await session.commit()
    root = settings.attachment_storage_dir
    await asyncio.gather(
        asyncio.to_thread(staging_path(root, storage_key).unlink, missing_ok=True),
        asyncio.to_thread(available_path(root, storage_key).unlink, missing_ok=True),
        asyncio.to_thread(processing_path(root, storage_key).unlink, missing_ok=True),
    )


async def run_forever(interval_seconds: int = 3) -> None:
    """Continuously process at most one private-media job at a time."""

    while True:
        try:
            processed = await scan_pending_once()
        except Exception:
            LOGGER.exception("attachment worker cycle failed")
            processed = False
        if not processed:
            await asyncio.sleep(max(interval_seconds, 1))


def main() -> None:
    """Start the bounded private media worker."""

    logging.basicConfig(level=logging.INFO)
    asyncio.run(run_forever())


if __name__ == "__main__":
    main()
