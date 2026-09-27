"""Self-contained file inventories for isolated migration containers."""

from __future__ import annotations

from dataclasses import asdict, dataclass
import hashlib
import json
from pathlib import Path
import sys


BUFFER_SIZE = 1024 * 1024


@dataclass(frozen=True)
class AttachmentInventory:
    """Aggregate attachment evidence that discloses no file paths."""

    file_count: int
    total_bytes: int
    aggregate_sha256: str


def _regular_files(root: Path) -> list[Path]:
    """Return sorted regular files while rejecting links and special entries."""

    values: list[Path] = []
    for path in sorted(root.rglob("*")):
        if path.is_symlink() or (not path.is_file() and not path.is_dir()):
            raise RuntimeError("inventory root contains a link or special entry")
        if path.is_file():
            values.append(path)
    return values


def _file_digest(path: Path) -> tuple[int, str]:
    digest = hashlib.sha256()
    size = 0
    with path.open("rb") as source:
        while chunk := source.read(BUFFER_SIZE):
            digest.update(chunk)
            size += len(chunk)
    return size, digest.hexdigest()


def attachment_inventory(root: Path) -> AttachmentInventory:
    """Hash attachment paths and bytes but expose only one aggregate digest."""

    aggregate = hashlib.sha256()
    total_bytes = 0
    files = _regular_files(root)
    for path in files:
        relative = path.relative_to(root).as_posix().encode("utf-8")
        size, digest = _file_digest(path)
        aggregate.update(len(relative).to_bytes(8, "big"))
        aggregate.update(relative)
        aggregate.update(size.to_bytes(8, "big"))
        aggregate.update(bytes.fromhex(digest))
        total_bytes += size
    return AttachmentInventory(len(files), total_bytes, aggregate.hexdigest())


def release_inventory(root: Path) -> dict[str, dict[str, object]]:
    """Return public immutable release paths, sizes, and hashes."""

    values: dict[str, dict[str, object]] = {}
    for path in _regular_files(root):
        size, digest = _file_digest(path)
        values[path.relative_to(root).as_posix()] = {
            "bytes": size,
            "sha256": digest,
        }
    return values


def _cli() -> None:
    if len(sys.argv) != 3 or sys.argv[1] not in {"attachments", "releases"}:
        raise SystemExit("usage: migration_file_inventory.py attachments|releases ROOT")
    root = Path(sys.argv[2])
    value = (
        asdict(attachment_inventory(root))
        if sys.argv[1] == "attachments"
        else release_inventory(root)
    )
    print(json.dumps(value, sort_keys=True))


if __name__ == "__main__":
    _cli()
