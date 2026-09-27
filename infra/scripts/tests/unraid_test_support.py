"""Shared helpers for the focused Unraid infrastructure tests."""

from __future__ import annotations

import os
from pathlib import Path
import shutil
import subprocess


SCRIPT_DIR = Path(__file__).resolve().parents[1]
COMPOSE_PATH = SCRIPT_DIR.parent / "compose.yaml"


def script(name: str) -> str:
    """Read one checked-in host script."""

    return (SCRIPT_DIR / name).read_text(encoding="utf-8")


def working_bash() -> str | None:
    """Find Bash without mistaking an unconfigured WSL shim for one."""

    candidates: list[str] = []
    if os.name == "nt":
        program_files = os.environ.get("ProgramFiles")
        if program_files:
            candidates.append(str(Path(program_files) / "Git" / "bin" / "bash.exe"))
    candidates.extend(["/bin/bash", shutil.which("bash") or ""])
    for candidate in dict.fromkeys(item for item in candidates if item):
        try:
            result = subprocess.run(
                [candidate, "--version"],
                check=False,
                capture_output=True,
                timeout=5,
            )
        except (OSError, subprocess.SubprocessError):
            continue
        if result.returncode == 0:
            return candidate
    return None


BASH = working_bash()


def run_bash(command: str, *arguments: str) -> subprocess.CompletedProcess[str]:
    """Run one focused sourced-function probe under the discovered Bash."""

    if BASH is None:
        raise RuntimeError("a functioning Bash is unavailable")
    return subprocess.run(
        [BASH, "-c", command, "unraid-test", *arguments],
        check=False,
        capture_output=True,
        text=True,
        timeout=10,
    )


def safe_share_config() -> str:
    """Return one complete cache-only, non-exported Unraid share config."""

    return (
        'shareUseCache="only"\n'
        'shareCachePool="cache"\n'
        'shareCachePool2=""\n'
        'shareExport="-"\n'
        'shareSecurity="private"\n'
        'shareExportNFS="-"\n'
        'shareSecurityNFS="private"\n'
    )
