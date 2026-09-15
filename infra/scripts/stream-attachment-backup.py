"""Write a deterministic attachment archive with an integrity manifest to stdout."""

from __future__ import annotations

import hashlib
import io
import json
import os
from pathlib import Path
import sys
import tarfile

ROOT = Path("/var/lib/little-orbit/attachments")
BUFFER_SIZE = 1024 * 1024


def digest(path: Path) -> str:
    """Return a streaming SHA-256 digest without retaining attachment bytes."""

    value = hashlib.sha256()
    with path.open("rb") as source:
        while chunk := source.read(BUFFER_SIZE):
            value.update(chunk)
    return value.hexdigest()


def regular_files() -> list[Path]:
    """Return stable regular-file paths and fail closed on links or special files."""

    files: list[Path] = []
    for current_root, directory_names, file_names in os.walk(ROOT, followlinks=False):
        base = Path(current_root)
        for name in directory_names:
            if (base / name).is_symlink():
                raise RuntimeError("attachment storage contains a symbolic link")
        for name in file_names:
            candidate = base / name
            if candidate.is_symlink() or not candidate.is_file():
                raise RuntimeError("attachment storage contains a non-regular file")
            files.append(candidate)
    return sorted(files, key=lambda item: item.relative_to(ROOT).as_posix())


def main() -> None:
    """Stream payload bytes followed by the matching bounded JSON manifest."""

    entries: list[dict[str, int | str]] = []
    with tarfile.open(fileobj=sys.stdout.buffer, mode="w|") as archive:
        for path in regular_files():
            relative = path.relative_to(ROOT).as_posix()
            stat = path.stat()
            entries.append({"path": relative, "bytes": stat.st_size, "sha256": digest(path)})
            info = archive.gettarinfo(str(path), arcname=f"payload/{relative}")
            info.uid = info.gid = 0
            info.uname = info.gname = ""
            with path.open("rb") as source:
                archive.addfile(info, source)
        encoded = json.dumps(entries, separators=(",", ":"), sort_keys=True).encode()
        manifest = tarfile.TarInfo("manifest.json")
        manifest.size = len(encoded)
        manifest.mode = 0o600
        archive.addfile(manifest, io.BytesIO(encoded))


if __name__ == "__main__":
    main()
