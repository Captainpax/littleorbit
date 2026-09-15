"""Validate and atomically restore an attachment archive received on stdin."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path, PurePosixPath
import shutil
import sys
import tarfile
from uuid import uuid4

ROOT = Path("/var/lib/little-orbit/attachments")
BUFFER_SIZE = 1024 * 1024


def safe_relative(name: str, prefix: str) -> Path:
    """Return a safe relative archive path below the requested prefix."""

    value = PurePosixPath(name)
    if value.is_absolute() or ".." in value.parts or not value.parts or value.parts[0] != prefix:
        raise RuntimeError("attachment archive contains an unsafe path")
    return Path(*value.parts[1:])


def receive_archive(staging: Path) -> list[dict[str, object]]:
    """Extract only regular payload files while calculating their digests."""

    observed: list[dict[str, object]] = []
    manifest: list[dict[str, object]] | None = None
    with tarfile.open(fileobj=sys.stdin.buffer, mode="r|*") as archive:
        for member in archive:
            if member.name == "manifest.json":
                source = archive.extractfile(member)
                if source is None or member.size > 8 * 1024 * 1024:
                    raise RuntimeError("attachment manifest is invalid")
                parsed = json.loads(source.read().decode("utf-8"))
                if not isinstance(parsed, list):
                    raise RuntimeError("attachment manifest is invalid")
                manifest = parsed
                continue
            relative = safe_relative(member.name, "payload")
            if not member.isfile():
                raise RuntimeError("attachment archive contains a non-regular payload")
            target = staging / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            source = archive.extractfile(member)
            if source is None:
                raise RuntimeError("attachment payload is unreadable")
            value = hashlib.sha256()
            count = 0
            with target.open("xb") as output:
                while chunk := source.read(BUFFER_SIZE):
                    output.write(chunk)
                    value.update(chunk)
                    count += len(chunk)
            observed.append({"path": relative.as_posix(), "bytes": count, "sha256": value.hexdigest()})
    if manifest is None or observed != manifest:
        raise RuntimeError("attachment archive integrity check failed")
    return observed


def replace_payload(staging: Path) -> None:
    """Swap validated bytes into the volume and roll back a partial swap."""

    rollback = ROOT / f".restore-old-{uuid4()}"
    rollback.mkdir(mode=0o700)
    moved_old: list[Path] = []
    moved_new: list[Path] = []
    try:
        for current in list(ROOT.iterdir()):
            if current in {staging, rollback}:
                continue
            destination = rollback / current.name
            current.rename(destination)
            moved_old.append(destination)
        for current in list(staging.iterdir()):
            destination = ROOT / current.name
            current.rename(destination)
            moved_new.append(destination)
    except Exception:
        for current in reversed(moved_new):
            if current.exists():
                current.rename(staging / current.name)
        for current in reversed(moved_old):
            if current.exists():
                current.rename(ROOT / current.name)
        raise
    finally:
        shutil.rmtree(staging, ignore_errors=True)
    shutil.rmtree(rollback)


def main() -> None:
    """Receive, verify, and replace attachment bytes without a plaintext host copy."""

    ROOT.mkdir(parents=True, exist_ok=True)
    staging = ROOT / f".restore-new-{uuid4()}"
    staging.mkdir(mode=0o700)
    try:
        receive_archive(staging)
        replace_payload(staging)
    except Exception:
        shutil.rmtree(staging, ignore_errors=True)
        raise


if __name__ == "__main__":
    main()
