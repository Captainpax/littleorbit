"""Filesystem and policy helpers for private attachment bytes."""

import hashlib
import re
import shutil
from pathlib import Path, PurePath

ALLOWED_MEDIA_TYPES = frozenset(
    {
        "image/jpeg",
        "image/png",
        "image/webp",
        "image/gif",
        "application/pdf",
        "text/plain",
        "text/markdown",
        "audio/mpeg",
        "audio/mp4",
        "audio/ogg",
        "video/mp4",
        "video/webm",
    }
)
MAX_FILE_BYTES = 100 * 1024 * 1024
COUPLE_QUOTA_BYTES = 2 * 1024 * 1024 * 1024
GLOBAL_QUOTA_BYTES = 50 * 1024 * 1024 * 1024
MIN_FREE_STORAGE_BYTES = 5 * 1024 * 1024 * 1024
MAX_CONCURRENT_UPLOADS_PER_COUPLE = 4
MAX_CHUNK_BYTES = 4 * 1024 * 1024
SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")


class AttachmentPolicyError(ValueError):
    """Raised when attachment metadata or byte offsets violate policy."""


def safe_file_name(value: str) -> str:
    """Return a display-only base name without path or control characters."""

    normalized = PurePath(value.replace("\\", "/")).name.strip()
    cleaned = "".join(character for character in normalized if ord(character) >= 32)
    if not cleaned or cleaned in {".", ".."}:
        raise AttachmentPolicyError("invalid_file_name")
    return cleaned[:255]


def validate_metadata(media_type: str, size_bytes: int, sha256: str) -> None:
    """Validate allow-listed type, bounded size, and normalized digest."""

    if media_type not in ALLOWED_MEDIA_TYPES:
        raise AttachmentPolicyError("unsupported_media_type")
    if not 0 < size_bytes <= MAX_FILE_BYTES:
        raise AttachmentPolicyError("file_too_large")
    if not SHA256_PATTERN.fullmatch(sha256):
        raise AttachmentPolicyError("invalid_sha256")


def validate_chunk(offset: int, chunk_size: int, total_size: int) -> None:
    """Reject gaps, oversized chunks, and writes beyond declared length."""

    if offset < 0 or chunk_size <= 0 or chunk_size > MAX_CHUNK_BYTES:
        raise AttachmentPolicyError("invalid_chunk")
    if offset + chunk_size > total_size:
        raise AttachmentPolicyError("chunk_exceeds_file")


def sha256_file(path: Path) -> str:
    """Hash a private file without loading it into memory."""

    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def has_upload_capacity(root: Path, incoming_bytes: int) -> bool:
    """Check the shared volume has room for an upload plus a fixed safety reserve."""

    root.mkdir(parents=True, exist_ok=True)
    return shutil.disk_usage(root).free >= incoming_bytes + MIN_FREE_STORAGE_BYTES


def staging_path(root: Path, storage_key: str) -> Path:
    """Resolve a server-generated staging key beneath the configured root."""

    return root / "staging" / f"{storage_key}.upload"


def available_path(root: Path, storage_key: str) -> Path:
    """Resolve sanitized available bytes beneath the configured root."""

    return root / "available" / storage_key


def processing_path(root: Path, storage_key: str) -> Path:
    """Resolve an unpublished sanitizer output on the same atomic filesystem."""

    return root / "processing" / f"{storage_key}.work"
