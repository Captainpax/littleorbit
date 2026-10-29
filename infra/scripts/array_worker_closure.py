"""Fail-closed offline wheel/base closure check. No resolver, download or build API."""

from __future__ import annotations

import argparse
import hashlib
import io
from importlib.metadata import version
import json
import os
from pathlib import Path
import platform
import re
import stat
import sys
from typing import Any
from zipfile import BadZipFile, ZipFile

SHA = re.compile(r"[0-9a-f]{64}")
BASE = re.compile(r"[a-z0-9./_-]+@sha256:[0-9a-f]{64}")


class ClosureError(ValueError):
    """Static refusal only; never echo a private path, filename or JSON key."""


def need(value: bool, reason: str) -> None:
    if not value:
        raise ClosureError(reason)


def fields(value: Any, expected: set[str]) -> dict[str, Any]:
    need(type(value) is dict and set(value) == expected, "CLOSURE_FIELDS")
    return value


def unique_pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        need(key not in result, "CLOSURE_DUPLICATE_KEY")
        result[key] = value
    return result


def regular_bytes(path: Path, maximum: int) -> bytes:
    """Build inputs only; this never reads accepted production payloads."""
    before = path.lstat()
    need(stat.S_ISREG(before.st_mode) and before.st_nlink == 1
         and 0 < before.st_size <= maximum, "CLOSURE_FILE_CUSTODY")
    descriptor = os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
    with os.fdopen(descriptor, "rb") as stream:
        held = os.fstat(stream.fileno())
        need(identity(before) == identity(held), "CLOSURE_FILE_CHANGED")
        data = stream.read(maximum + 1)
        need(identity(held) == identity(os.fstat(stream.fileno())), "CLOSURE_FILE_CHANGED")
    need(identity(before) == identity(path.lstat()) and len(data) == before.st_size,
         "CLOSURE_FILE_CHANGED")
    return data


def identity(value: os.stat_result) -> tuple[int, ...]:
    return (value.st_dev, value.st_ino, value.st_mode, value.st_uid, value.st_gid,
            value.st_nlink, value.st_size, value.st_mtime_ns,
            value.st_ctime_ns if os.name != "nt" else 0)


def validate_manifest(value: Any, expected_base: str) -> dict[str, Any]:
    manifest = fields(value, {"schema", "status", "base", "source", "wheels",
                              "originalImageMetadata"})
    need(manifest["schema"] == "LITTLE_ORBIT_OFFLINE_WORKER_CLOSURE_V1"
         and manifest["status"] == "SEALED_OFFLINE_INPUTS", "CLOSURE_UNSEALED")
    validate_base(manifest["base"], expected_base)
    source = fields(manifest["source"], {"gitCommit", "treeSha256", "reviewReceiptSha256"})
    need(type(source["gitCommit"]) is str and re.fullmatch(r"[0-9a-f]{40}", source["gitCommit"])
         is not None, "CLOSURE_SOURCE_PIN")
    for key in ("treeSha256", "reviewReceiptSha256"):
        need(type(source[key]) is str and SHA.fullmatch(source[key]) is not None, "CLOSURE_SOURCE_PIN")
    metadata = manifest["originalImageMetadata"]
    need(type(metadata) is str and SHA.fullmatch(metadata) is not None, "CLOSURE_CACHE_METADATA_PENDING")
    wheels = manifest["wheels"]
    need(type(wheels) is list and 2 <= len(wheels) <= 512, "CLOSURE_WHEELS_PENDING")
    return manifest


def validate_base(value: Any, expected_base: str) -> None:
    base = fields(value, {"reference", "configSha256", "metadataSha256", "os",
                          "architecture", "pythonVersion", "pipVersion", "entrypoint"})
    need(type(expected_base) is str and BASE.fullmatch(expected_base) is not None
         and base["reference"] == expected_base, "CLOSURE_BASE_PIN")
    for name in ("configSha256", "metadataSha256"):
        need(type(base[name]) is str and SHA.fullmatch(base[name]) is not None, "CLOSURE_BASE_METADATA")
    need((base["os"], base["architecture"], base["pythonVersion"]) ==
         ("linux", "amd64", "3.12.11"), "CLOSURE_BASE_ABI")
    need(type(base["pipVersion"]) is str and re.fullmatch(r"[0-9]+(?:\.[0-9]+){1,3}",
         base["pipVersion"]) is not None, "CLOSURE_PIP_METADATA_PENDING")
    need(base["entrypoint"] is None or type(base["entrypoint"]) is list
         and not base["entrypoint"], "CLOSURE_BASE_ENTRYPOINT")


def validate_runtime(manifest: dict[str, Any]) -> None:
    """Build-step check against actual interpreter/installer, not claimed metadata."""
    need(platform.system() == "Linux" and platform.machine() == "x86_64", "CLOSURE_RUNTIME_ABI")
    need(platform.python_version() == manifest["base"]["pythonVersion"], "CLOSURE_RUNTIME_PYTHON")
    need(version("pip") == manifest["base"]["pipVersion"], "CLOSURE_RUNTIME_PIP")


def wheel_record(value: Any) -> dict[str, Any]:
    row = fields(value, {"distribution", "version", "filename", "bytes", "sha256"})
    need(type(row["distribution"]) is str and re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*",
         row["distribution"]) is not None, "CLOSURE_DISTRIBUTION")
    need(type(row["version"]) is str and re.fullmatch(r"[0-9][a-zA-Z0-9.!+_-]*", row["version"])
         is not None, "CLOSURE_VERSION")
    filename = row["filename"]
    need(type(filename) is str and re.fullmatch(r"[a-zA-Z0-9_.+!-]+\.whl", filename)
         is not None, "CLOSURE_WHEEL_FILENAME")
    need(type(row["bytes"]) is int and 0 < row["bytes"] <= 512 * 1024**2, "CLOSURE_WHEEL_SIZE")
    need(type(row["sha256"]) is str and SHA.fullmatch(row["sha256"]) is not None,
         "CLOSURE_WHEEL_HASH")
    return row


def wheel_metadata(data: bytes, row: dict[str, Any]) -> None:
    """Bind declared identity to wheel metadata, not only the install filename."""
    with ZipFile(io.BytesIO(data)) as archive:
        names = [name for name in archive.namelist() if name.endswith(".dist-info/METADATA")]
        need(len(names) == 1, "CLOSURE_WHEEL_METADATA")
        need(archive.getinfo(names[0]).file_size <= 1024**2, "CLOSURE_WHEEL_METADATA")
        content = archive.read(names[0]).decode("utf-8")
    name = re.findall(r"^Name: ([^\r\n]+)\r?$", content, re.MULTILINE)
    version = re.findall(r"^Version: ([^\r\n]+)\r?$", content, re.MULTILINE)
    need(len(name) == len(version) == 1, "CLOSURE_WHEEL_METADATA")
    canonical = re.sub(r"[-_.]+", "-", name[0]).lower()
    need(canonical == row["distribution"] and version == [row["version"]], "CLOSURE_WHEEL_IDENTITY")


def requirements(manifest: dict[str, Any], root: Path) -> str:
    """Check every exact wheel once; transitive completeness is also pip-check gated."""
    rows = [wheel_record(value) for value in manifest["wheels"]]
    names = [row["distribution"] for row in rows]
    filenames = [row["filename"] for row in rows]
    need(len(set(names)) == len(names) and len(set(filenames)) == len(filenames),
         "CLOSURE_DUPLICATE_WHEEL")
    need({"little-orbit-api", "little-orbit-ai"} <= set(names), "CLOSURE_PROJECT_WHEELS")
    need(root.is_dir() and not root.is_symlink(), "CLOSURE_WHEEL_ROOT")
    need({path.name for path in root.iterdir()} == set(filenames), "CLOSURE_EXTRA_INPUT")
    need(sum(row["bytes"] for row in rows) <= 2 * 1024**3, "CLOSURE_TOTAL_SIZE")
    for row in rows:
        path = root / row["filename"]
        data = regular_bytes(path, 512 * 1024**2)
        need(len(data) == row["bytes"] and hashlib.sha256(data).hexdigest() == row["sha256"],
             "CLOSURE_WHEEL_CHANGED")
        wheel_metadata(data, row)
    return "".join(f"{row['distribution']}=={row['version']} --hash=sha256:{row['sha256']}\n"
                   for row in sorted(rows, key=lambda row: row["distribution"]))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--wheel-root", type=Path, required=True)
    parser.add_argument("--expected-base", required=True)
    parser.add_argument("--check-runtime", action="store_true")
    args = parser.parse_args()
    try:
        value = json.loads(regular_bytes(args.manifest, 1024**2), object_pairs_hook=unique_pairs)
        manifest = validate_manifest(value, args.expected_base)
        if args.check_runtime:
            validate_runtime(manifest)
        result = requirements(manifest, args.wheel_root)
    except (ClosureError, OSError, ValueError, BadZipFile, KeyError):
        print("OFFLINE_WORKER_CLOSURE_REFUSED", file=sys.stderr)
        return 78
    print(result, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
