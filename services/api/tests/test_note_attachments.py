"""Focused policy and sanitizer tests for private note attachments."""

from pathlib import Path

import pytest
from fastapi import HTTPException, Request
from PIL import Image
from pypdf import PdfWriter

from little_orbit_api.attachment_media import sanitize_file
from little_orbit_api.attachment_storage import (
    MAX_CHUNK_BYTES,
    AttachmentPolicyError,
    safe_file_name,
    sha256_file,
    validate_chunk,
    validate_metadata,
)
from little_orbit_api.database import Base
from little_orbit_api.routes.attachments import _read_chunk


def test_media_worker_registers_attachment_foreign_key_tables() -> None:
    """The standalone worker can flush claims without mapper resolution failures."""

    assert {"accounts", "couples", "notes", "note_attachments"} <= set(
        Base.metadata.tables
    )


def test_attachment_policy_accepts_supported_bounded_metadata() -> None:
    """A normalized supported attachment is accepted."""

    validate_metadata("image/jpeg", 1024, "a" * 64)
    assert safe_file_name("../../private/photo.jpg") == "photo.jpg"
    validate_chunk(0, MAX_CHUNK_BYTES, MAX_CHUNK_BYTES)


@pytest.mark.parametrize(
    ("media_type", "size", "digest"),
    [
        ("application/zip", 20, "a" * 64),
        ("image/jpeg", 0, "a" * 64),
        ("image/jpeg", 100 * 1024 * 1024 + 1, "a" * 64),
        ("image/jpeg", 20, "not-a-digest"),
    ],
)
def test_attachment_policy_rejects_untrusted_metadata(
    media_type: str, size: int, digest: str
) -> None:
    """Unsupported types, invalid sizes, and malformed hashes fail closed."""

    with pytest.raises(AttachmentPolicyError):
        validate_metadata(media_type, size, digest)


def test_chunk_policy_rejects_gaps_and_declared_size_overflow() -> None:
    """A client cannot smuggle extra bytes beyond the reserved quota."""

    with pytest.raises(AttachmentPolicyError):
        validate_chunk(10, MAX_CHUNK_BYTES + 1, MAX_CHUNK_BYTES * 2)
    with pytest.raises(AttachmentPolicyError):
        validate_chunk(8, 4, 10)


def test_image_sanitizer_removes_exif_metadata(tmp_path: Path) -> None:
    """Available image bytes exclude source EXIF metadata."""

    source = tmp_path / "source.jpg"
    target = tmp_path / "target"
    image = Image.new("RGB", (12, 12), "red")
    exif = Image.Exif()
    exif[0x010E] = "private description"
    image.save(source, exif=exif)

    sanitize_file(source, target, "image/jpeg")

    with Image.open(target) as sanitized:
        assert sanitized.getexif().get(0x010E) is None
    assert sha256_file(target) != sha256_file(source)


def test_pdf_sanitizer_discards_document_metadata(tmp_path: Path) -> None:
    """A PDF remains readable while author metadata is removed."""

    source = tmp_path / "source.pdf"
    target = tmp_path / "target"
    writer = PdfWriter()
    writer.add_blank_page(width=72, height=72)
    writer.add_metadata({"/Author": "Private Person"})
    with source.open("wb") as output:
        writer.write(output)

    sanitize_file(source, target, "application/pdf")

    from pypdf import PdfReader

    reader = PdfReader(target)
    assert reader.metadata is None or not reader.metadata.get("/Author")


def test_gif_sanitizer_keeps_animation_readable(tmp_path: Path) -> None:
    """Animated GIFs remain valid after per-frame metadata removal."""

    source = tmp_path / "source.gif"
    target = tmp_path / "target"
    frames = [Image.new("RGB", (8, 8), color) for color in ("red", "blue")]
    frames[0].save(source, save_all=True, append_images=frames[1:], duration=20, loop=0)

    sanitize_file(source, target, "image/gif")

    with Image.open(target) as sanitized:
        assert getattr(sanitized, "n_frames", 1) == 2


@pytest.mark.asyncio
async def test_chunk_reader_rejects_stream_over_limit_without_full_buffer() -> None:
    """A missing Content-Length cannot bypass the four-MiB body bound."""

    calls = 0

    async def receive() -> dict[str, object]:
        nonlocal calls
        calls += 1
        return {
            "type": "http.request",
            "body": b"x" * (MAX_CHUNK_BYTES // 2 + 1),
            "more_body": calls == 1,
        }

    request = Request({"type": "http", "method": "PUT", "headers": []}, receive)
    with pytest.raises(HTTPException) as raised:
        await _read_chunk(request)
    assert raised.value.status_code == 413
