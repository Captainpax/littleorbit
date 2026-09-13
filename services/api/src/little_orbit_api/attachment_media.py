"""Fail-closed malware scanning and metadata removal for note attachments."""

import asyncio
import logging
import shutil
import socket
import struct
import subprocess
import tempfile
from collections.abc import Callable
from pathlib import Path
from uuid import UUID

from PIL import Image, ImageSequence
from pypdf import PdfReader, PdfWriter
from sqlalchemy import func, select, update

from . import models as _models  # noqa: F401  # Register FK target tables for worker flushes.
from .activity_service import record_activity
from .attachment_models import NoteAttachment
from .attachment_storage import (
    COUPLE_QUOTA_BYTES,
    MAX_FILE_BYTES,
    available_path,
    sha256_file,
    staging_path,
)
from .clock import SystemClock
from .config import Settings, get_settings
from .database import SessionFactory

LOGGER = logging.getLogger(__name__)
Image.MAX_IMAGE_PIXELS = 80_000_000


class ScanUnavailable(RuntimeError):
    """Raised when scanning or sanitization cannot safely finish."""


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


def sanitize_file(source: Path, target: Path, media_type: str) -> None:
    """Write a metadata-free copy using the handler for its allow-listed type."""

    target.parent.mkdir(parents=True, exist_ok=True)
    if media_type.startswith("image/"):
        _sanitize_image(source, target, media_type)
    elif media_type == "application/pdf":
        _sanitize_pdf(source, target)
    elif media_type.startswith(("audio/", "video/")):
        _sanitize_media(source, target, media_type)
    else:
        _sanitize_text(source, target)


def _sanitize_image(source: Path, target: Path, media_type: str) -> None:
    image_format = {
        "image/jpeg": "JPEG",
        "image/png": "PNG",
        "image/webp": "WEBP",
        "image/gif": "GIF",
    }[media_type]
    with Image.open(source) as image:
        frames: list[Image.Image] = []
        durations: list[int] = []
        pixel_count = 0
        for source_frame in ImageSequence.Iterator(image):
            if len(frames) >= 300:
                raise ScanUnavailable("too_many_image_frames")
            pixel_count += source_frame.width * source_frame.height
            if pixel_count > 80_000_000:
                raise ScanUnavailable("image_pixel_budget_exceeded")
            durations.append(
                int(source_frame.info.get("duration", image.info.get("duration", 100)))
            )
            frames.append(_clean_frame(source_frame, image_format))
        if not frames:
            raise ScanUnavailable("invalid_image")
        if len(frames) > 1 and image_format in {"GIF", "WEBP"}:
            frames[0].save(
                target,
                format=image_format,
                save_all=True,
                append_images=frames[1:],
                duration=durations,
                loop=image.info.get("loop", 0),
                disposal=2,
            )
        elif image_format == "JPEG":
            frames[0].save(target, format=image_format, quality=90, optimize=True)
        else:
            frames[0].save(target, format=image_format)


def _clean_frame(frame: Image.Image, image_format: str) -> Image.Image:
    if image_format == "GIF":
        # Copy pixels into a fresh image so Pillow cannot carry a palette index
        # or transparency entry from the untrusted source into the encoder.
        clean = Image.new("RGBA", frame.size, (0, 0, 0, 0))
        clean.alpha_composite(frame.convert("RGBA"))
        return clean
    mode = "RGB" if image_format == "JPEG" else "RGBA"
    clean = Image.new(mode, frame.size)
    clean.paste(frame.convert(mode))
    return clean


def _sanitize_pdf(source: Path, target: Path) -> None:
    reader = PdfReader(str(source), strict=True)
    writer = PdfWriter()
    for page in reader.pages:
        writer.add_page(page)
    writer.metadata = None
    with target.open("wb") as output:
        writer.write(output)


def _sanitize_text(source: Path, target: Path) -> None:
    text = source.read_text(encoding="utf-8")
    if "\x00" in text:
        raise ScanUnavailable("invalid_text")
    target.write_text(text, encoding="utf-8", newline="")


def _sanitize_media(source: Path, target: Path, media_type: str) -> None:
    suffix = {
        "audio/mpeg": ".mp3",
        "audio/mp4": ".m4a",
        "audio/ogg": ".ogg",
        "video/mp4": ".mp4",
        "video/webm": ".webm",
    }[media_type]
    with tempfile.TemporaryDirectory() as directory:
        temporary = Path(directory) / f"sanitized{suffix}"
        command = [
            "ffmpeg",
            "-nostdin",
            "-v",
            "error",
            "-i",
            str(source),
            "-map",
            "0",
            "-map_metadata",
            "-1",
            "-map_chapters",
            "-1",
            "-c",
            "copy",
            str(temporary),
        ]
        result = subprocess.run(command, capture_output=True, timeout=120, check=False)
        if result.returncode != 0 or not temporary.is_file():
            raise ScanUnavailable("invalid_media")
        shutil.move(temporary, target)


async def scan_pending_once(
    settings: Settings | None = None,
    scanner: Callable[[Path, str, int], bool] = clamav_scan,
) -> bool:
    """Claim and process one pending attachment, leaving outages retryable."""

    effective = settings or get_settings()
    attachment_id = await _claim_pending()
    if attachment_id is None:
        return False
    try:
        await _process(attachment_id, effective, scanner)
    except ScanUnavailable as error:
        LOGGER.warning("attachment scan deferred: %s", error)
        await _set_status(attachment_id, "pending_scan")
    except Exception:
        LOGGER.exception("attachment processing failed")
        await _reject(attachment_id, effective, "processing_failed")
    return True


async def _claim_pending() -> UUID | None:
    async with SessionFactory() as session:
        item = await session.scalar(
            select(NoteAttachment)
            .where(NoteAttachment.status == "pending_scan")
            .order_by(NoteAttachment.created_at)
            .with_for_update(skip_locked=True)
        )
        if item is None:
            return None
        item.status = "scanning"
        item.updated_at = SystemClock().now()
        await session.commit()
        return item.id


async def _process(
    attachment_id: UUID,
    settings: Settings,
    scanner: Callable[[Path, str, int], bool],
) -> None:
    async with SessionFactory() as session:
        item = await session.get(NoteAttachment, attachment_id)
        if item is None or item.status != "scanning":
            return
        source = staging_path(settings.attachment_storage_dir, item.storage_key)
        target = available_path(settings.attachment_storage_dir, item.storage_key)
        media_type = item.media_type
    clean = await asyncio.to_thread(scanner, source, settings.clamav_host, settings.clamav_port)
    if not clean:
        await _reject(attachment_id, settings, "malware_detected")
        return
    await asyncio.to_thread(sanitize_file, source, target, media_type)
    final_size = target.stat().st_size
    if final_size > MAX_FILE_BYTES:
        await _reject(attachment_id, settings, "sanitized_file_too_large")
        return
    sanitized_hash = await asyncio.to_thread(sha256_file, target)
    if not await _mark_available(attachment_id, settings, sanitized_hash, final_size):
        await _reject(attachment_id, settings, "couple_quota_exceeded_after_sanitization")
        return
    await asyncio.to_thread(source.unlink, True)


async def _mark_available(
    attachment_id: UUID,
    settings: Settings,
    sanitized_hash: str,
    final_size: int,
) -> bool:
    async with SessionFactory() as lookup:
        couple_id = await lookup.scalar(
            select(NoteAttachment.couple_id).where(NoteAttachment.id == attachment_id)
        )
        if couple_id is None:
            return False
    async with SessionFactory() as session:
        # The reservation used the uploaded size. Sanitizers may legitimately
        # grow a file, so atomically charge only the positive final-size delta.
        from .couple_access import lock_couple

        await lock_couple(session, couple_id)
        item = await session.get(NoteAttachment, attachment_id, with_for_update=True)
        if item is None or item.status != "scanning":
            return False
        charged = await session.scalar(
            select(func.coalesce(func.sum(NoteAttachment.size_bytes), 0)).where(
                NoteAttachment.couple_id == couple_id,
                NoteAttachment.deleted_at.is_(None),
                NoteAttachment.status.in_(("uploading", "pending_scan", "scanning", "available")),
                NoteAttachment.id != attachment_id,
            )
        )
        if int(charged or 0) + final_size > COUPLE_QUOTA_BYTES:
            return False
        now = SystemClock().now()
        item.status = "available"
        item.sha256 = sanitized_hash
        item.size_bytes = final_size
        item.uploaded_bytes = item.size_bytes
        item.scanned_at = now
        item.updated_at = now
        await record_activity(
            session, couple_id, item.uploaded_by, "attachment_available",
            f"attachment:available:{item.id}", target_type="note",
            target_id=item.note_id,
        )
        await session.commit()
        return True


async def _set_status(attachment_id: UUID, value: str) -> None:
    async with SessionFactory() as session:
        await session.execute(
            update(NoteAttachment)
            .where(NoteAttachment.id == attachment_id, NoteAttachment.status == "scanning")
            .values(status=value, updated_at=SystemClock().now())
        )
        await session.commit()


async def _reject(attachment_id: UUID, settings: Settings, reason: str) -> None:
    async with SessionFactory() as session:
        item = await session.get(NoteAttachment, attachment_id, with_for_update=True)
        if item is None:
            return
        item.status = "rejected"
        item.rejection_reason = reason
        item.updated_at = SystemClock().now()
        storage_key = item.storage_key
        await session.commit()
    await asyncio.gather(
        asyncio.to_thread(staging_path(settings.attachment_storage_dir, storage_key).unlink, True),
        asyncio.to_thread(available_path(settings.attachment_storage_dir, storage_key).unlink, True),
    )


async def run_forever(interval_seconds: int = 3) -> None:
    """Continuously scan private uploads without exposing unscanned bytes."""

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
