#!/usr/bin/env python3
"""Read-only admission and quiet configuration validation, never lifecycle actions."""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
from pathlib import Path
import stat
import subprocess
import sys

# The reviewed controller may use Python -I; import only this sibling code root.
# Deployment must seal both files, not replace an existing launcher adapter.
sys.path.insert(0, str(Path(__file__).resolve().parent))
from array_recovery_admission import AdmissionError, ROOT, admit, read_sealed_json, require


def private_environment_file(path: Path) -> None:
    """Validate custody without reading or printing any runtime secret."""
    info = path.lstat()
    require(stat.S_ISREG(info.st_mode) and not path.is_symlink(), "Unsafe runtime environment")
    require(info.st_uid == info.st_gid == 0 and info.st_nlink == 1
            and stat.S_IMODE(info.st_mode) == 0o600, "Runtime environment custody differs")
    parent = path.parent.lstat()
    require(stat.S_ISDIR(parent.st_mode) and not path.parent.is_symlink()
            and parent.st_uid == parent.st_gid == 0 and stat.S_IMODE(parent.st_mode) == 0o700,
            "Runtime secret directory custody differs")


def verify_compose_sources(descriptors: list[dict[str, object]]) -> list[str]:
    """Bind configuration bytes to caller-reviewed source digests."""
    repo = f"{ROOT}/deploy/repo"
    expected = [f"{repo}/infra/{name}" for name in (
        "compose.yaml", "compose.rx480.yaml", "compose.array-recovery.yaml",
    )]
    require(len(descriptors) == len(expected), "Wrong Compose source count")
    for item, expected_path in zip(descriptors, expected, strict=True):
        require(set(item) == {"path", "sha256", "bytes"}, "Invalid Compose descriptor")
        require(item["path"] == expected_path, "Wrong Compose source path/order")
        path = Path(expected_path)
        require(not path.is_symlink() and path.is_file(), "Unsafe Compose source")
        require(type(item["bytes"]) is int and 0 < item["bytes"] <= 1024**2,
                "Invalid Compose source bound")
        with path.open("rb") as handle:
            payload = handle.read(1024**2 + 1)
        require(len(payload) == item["bytes"]
                and hashlib.sha256(payload).hexdigest() == item["sha256"],
                "Compose source bytes differ from reviewed input")
    return expected


def quiet_compose(paths: list[str]) -> None:
    """Invoke only config --quiet; suppress secret-bearing native error output."""
    require(sys.platform == "linux" and os.geteuid() == 0, "Quiet Compose requires target root")
    require(os.uname().nodename.split(".", maxsplit=1)[0] == "na-west-2", "Wrong execution host")
    env_file = Path(f"{ROOT}/secrets/runtime.env")
    private_environment_file(env_file)
    command = [
        "/usr/bin/docker", "--host", "unix:///var/run/docker.sock", "compose",
        "--project-name", "little-orbit-recovery", "--project-directory", f"{ROOT}/deploy/repo/infra",
        "--env-file", str(env_file),
    ]
    for path in paths:
        command.extend(["-f", path])
    command.extend(["config", "--quiet"])
    result = subprocess.run(command, env={"PATH": "/usr/bin:/bin", "LC_ALL": "C"},
                            stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                            stderr=subprocess.DEVNULL, timeout=30, check=False)
    require(result.returncode == 0, "Quiet Compose validation failed; sensitive output withheld")


def arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("admit", "validate", "quiet-compose"))
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--manifest-sha256", required=True)
    parser.add_argument("--compose-descriptors", type=Path)
    parser.add_argument("--compose-descriptors-sha256")
    return parser.parse_args()


def main() -> int:
    args = arguments()
    try:
        manifest, _ = read_sealed_json(args.manifest, args.manifest_sha256)
        result = admit(manifest, dt.datetime.now(dt.timezone.utc))
        if args.mode == "quiet-compose":
            require(args.compose_descriptors is not None
                    and args.compose_descriptors_sha256 is not None, "Pinned Compose descriptors required")
            source, _ = read_sealed_json(args.compose_descriptors, args.compose_descriptors_sha256)
            require(set(source) == {"recordType", "files"}
                    and source["recordType"] == "little-orbit-array-compose-sources/v1"
                    and isinstance(source["files"], list), "Invalid Compose sources index")
            paths = verify_compose_sources(source["files"])
            quiet_compose(paths)
            result["quietCompose"] = "CONFIG_SYNTAX_ONLY_NOT_DEPLOYMENT_ACCEPTANCE"
        print(json.dumps(result, sort_keys=True, separators=(",", ":")))
        return 0
    except (AdmissionError, OSError, subprocess.SubprocessError, TypeError, KeyError) as error:
        message = str(error) if isinstance(error, AdmissionError) else "Read-only admission failed"
        print(json.dumps({"stage": "BLOCKED_PRESERVE_EVIDENCE", "error": message}), file=sys.stderr)
        return 78


if __name__ == "__main__":
    raise SystemExit(main())
