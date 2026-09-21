"""Stream-verify an attachment backup without writing relationship content."""

from __future__ import annotations

import hashlib
import json
from pathlib import PurePosixPath
import sys
import tarfile

BUFFER_SIZE = 1024 * 1024
MAX_MANIFEST_BYTES = 8 * 1024 * 1024


def safe_payload_path(name: str) -> str:
    """Return a normalized payload path or reject traversal and non-payload entries."""

    value = PurePosixPath(name)
    if value.is_absolute() or ".." in value.parts or len(value.parts) < 2:
        raise RuntimeError("attachment archive contains an unsafe path")
    if value.parts[0] != "payload":
        raise RuntimeError("attachment archive contains an unexpected entry")
    return PurePosixPath(*value.parts[1:]).as_posix()


def verify() -> None:
    """Verify every streamed byte against the terminal archive manifest."""

    observed: list[dict[str, object]] = []
    expected: list[dict[str, object]] | None = None
    with tarfile.open(fileobj=sys.stdin.buffer, mode="r|*") as archive:
        for member in archive:
            source = archive.extractfile(member)
            if member.name == "manifest.json":
                if source is None or not member.isfile() or member.size > MAX_MANIFEST_BYTES:
                    raise RuntimeError("attachment manifest is invalid")
                parsed = json.loads(source.read().decode("utf-8"))
                if not isinstance(parsed, list):
                    raise RuntimeError("attachment manifest is invalid")
                expected = parsed
                continue
            if source is None or not member.isfile():
                raise RuntimeError("attachment archive contains a non-regular payload")
            relative = safe_payload_path(member.name)
            digest = hashlib.sha256()
            count = 0
            while chunk := source.read(BUFFER_SIZE):
                digest.update(chunk)
                count += len(chunk)
            observed.append({"path": relative, "bytes": count, "sha256": digest.hexdigest()})
    if expected is None or observed != expected:
        raise RuntimeError("attachment archive integrity check failed")


if __name__ == "__main__":
    verify()
