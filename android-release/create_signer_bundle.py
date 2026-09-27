#!/usr/bin/env python3
"""Convert the legacy Little Orbit signer environment into one age-encrypted bundle."""

from __future__ import annotations

import argparse
import io
import os
import shutil
import subprocess
import sys
import tarfile
from pathlib import Path

EXPECTED_KEYS = {
    "ANDROID_SIGNING_STORE_FILE",
    "ANDROID_SIGNING_STORE_PASSWORD",
    "ANDROID_SIGNING_KEY_ALIAS",
    "ANDROID_SIGNING_KEY_PASSWORD",
}


class BundleError(RuntimeError):
    """A signer bundle could not be created safely."""


def _normalise_value(raw_value: str) -> str:
    value = raw_value.strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
        value = value[1:-1]
    if not value or "\n" in value or "\r" in value:
        raise BundleError("signing environment contains an empty or multiline value")
    return value


def _environment_entry(raw_line: str, existing: dict[str, str]) -> tuple[str, str] | None:
    line = raw_line.strip()
    if not line or line.startswith("#"):
        return None
    key, separator, raw_value = line.partition("=")
    if separator != "=" or key not in EXPECTED_KEYS or key in existing:
        raise BundleError("signing environment contains an unexpected or duplicate key")
    return key, _normalise_value(raw_value)


def _parse_environment(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        entry = _environment_entry(raw_line, values)
        if entry is not None:
            values[entry[0]] = entry[1]
    if values.keys() != EXPECTED_KEYS:
        raise BundleError("signing environment is incomplete")
    return values


def _archive(values: dict[str, str], environment: Path) -> bytes:
    store = Path(values["ANDROID_SIGNING_STORE_FILE"])
    if not store.is_absolute():
        store = environment.parent / store
    store = store.resolve(strict=True)
    files = {
        "release.p12": store.read_bytes(),
        "store-password": values["ANDROID_SIGNING_STORE_PASSWORD"].encode(),
        "key-alias": values["ANDROID_SIGNING_KEY_ALIAS"].encode(),
        "key-password": values["ANDROID_SIGNING_KEY_PASSWORD"].encode(),
    }
    stream = io.BytesIO()
    with tarfile.open(fileobj=stream, mode="w") as archive:
        for name, content in files.items():
            info = tarfile.TarInfo(name)
            info.size = len(content)
            info.mode = 0o600
            info.uid = 0
            info.gid = 0
            info.mtime = 0
            archive.addfile(info, io.BytesIO(content))
    return stream.getvalue()


def _resolve_age(value: str) -> Path:
    candidate = Path(value)
    if candidate.name == value:
        found = shutil.which(value)
        if found is None:
            raise BundleError("age executable is unavailable")
        candidate = Path(found)
    elif not candidate.is_absolute():
        raise BundleError("age executable path must be absolute")
    candidate = candidate.resolve(strict=True)
    if not candidate.is_file() or not os.access(candidate, os.X_OK):
        raise BundleError("age executable is not executable")
    return candidate


def create_bundle(environment: Path, recipient: str, output: Path, age_binary: Path) -> None:
    environment = environment.resolve(strict=True)
    output = output.resolve()
    repository = Path(__file__).resolve().parents[1]
    try:
        output.relative_to(repository)
    except ValueError:
        pass
    else:
        raise BundleError("signer bundle must be written outside the repository")
    if output.exists():
        raise BundleError("refusing to overwrite an existing signer bundle")
    output.parent.mkdir(parents=True, exist_ok=True)
    result = subprocess.run(
        [str(age_binary), "--encrypt", "--recipient", recipient, "--output", str(output)],
        input=_archive(_parse_environment(environment), environment),
        capture_output=True,
        check=False,
    )
    if result.returncode != 0:
        output.unlink(missing_ok=True)
        raise BundleError("age could not encrypt the signer bundle")
    try:
        os.chmod(output, 0o600)
    except OSError:
        pass


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--environment", type=Path, required=True)
    parser.add_argument("--recipient", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument(
        "--age-bin",
        default=os.environ.get("ANDROID_RELEASE_AGE_BIN", "age"),
        help="absolute age path, or the bare name resolved once from PATH",
    )
    args = parser.parse_args()
    try:
        create_bundle(args.environment, args.recipient, args.output, _resolve_age(args.age_bin))
    except (OSError, ValueError, BundleError) as error:
        print(f"bundle error: {error}", file=sys.stderr)
        return 2
    print(f"Encrypted signer bundle created: {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
