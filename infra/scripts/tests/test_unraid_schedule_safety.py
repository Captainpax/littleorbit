"""Scheduled-operation invariants for the fixed Unraid host."""

from __future__ import annotations

import json
from pathlib import Path
import subprocess

import pytest

from infra.scripts.tests.unraid_test_support import (
    BASH,
    SCRIPT_DIR,
    run_bash,
)


@pytest.mark.skipif(BASH is None, reason="a functioning Bash is unavailable")
def test_schedule_metadata_is_disabled_by_default_and_activation_is_exact(
    tmp_path: Path,
) -> None:
    """The schedule transition preserves foreign entries and enables exact jobs."""

    installer = SCRIPT_DIR / "unraid-install-user-scripts.sh"
    schedule = tmp_path / "schedule.json"
    schedule.write_text(
        '{"foreign":{"frequency":"daily"},'
        '"test/scripts/little-orbit-backup/script":{'
        '"script":"test/scripts/little-orbit-backup/script",'
        '"frequency":"custom"}}\n',
        encoding="utf-8",
    )

    def invoke(mode: str) -> subprocess.CompletedProcess[str]:
        return run_bash(
            'source "$1"; write_schedules "$2" "$3" test/scripts',
            installer.resolve().as_posix(),
            mode,
            schedule.resolve().as_posix(),
        )

    def write(mode: str) -> dict[str, dict[str, str]]:
        result = invoke(mode)
        assert result.returncode == 0, result.stderr
        return json.loads(schedule.read_text(encoding="utf-8"))

    inactive = write("install")
    assert inactive["foreign"] == {"frequency": "daily"}
    little_orbit = {
        key: value for key, value in inactive.items() if key.startswith("test/scripts/")
    }
    assert len(little_orbit) == 4
    assert {entry["frequency"] for entry in little_orbit.values()} == {"disabled"}
    assert {entry["custom"] for entry in little_orbit.values()} == {""}

    active = write("activate-after-cutover")
    assert active["test/scripts/little-orbit-startup/script"]["frequency"] == "start"
    custom_entries = [
        entry
        for path, entry in active.items()
        if path.startswith("test/scripts/") and "startup" not in path
    ]
    assert {entry["frequency"] for entry in custom_entries} == {"custom"}
    assert {entry["custom"] for entry in custom_entries} == {
        "*/5 * * * *",
        "0 8 * * *",
        "0 7 * * 2",
    }


@pytest.mark.skipif(BASH is None, reason="a functioning Bash is unavailable")
def test_schedule_metadata_rejects_aliases_without_rewriting(tmp_path: Path) -> None:
    """Noncanonical or foreign Little Orbit schedule identities fail unchanged."""

    installer = SCRIPT_DIR / "unraid-install-user-scripts.sh"
    schedule = tmp_path / "schedule.json"
    for unexpected_path in (
        "test/scripts/other/../little-orbit-backup/script",
        "test/scripts/little-orbit-personal/script",
    ):
        original = json.dumps(
            {unexpected_path: {"script": unexpected_path, "frequency": "custom"}}
        ).encode()
        schedule.write_bytes(original)
        rejected = run_bash(
            'source "$1"; write_schedules install "$2" test/scripts',
            installer.resolve().as_posix(),
            schedule.resolve().as_posix(),
        )
        assert rejected.returncode == 78
        assert schedule.read_bytes() == original


@pytest.mark.skipif(BASH is None, reason="a functioning Bash is unavailable")
def test_cron_transition_preserves_unrelated_bytes_and_is_idempotent(
    tmp_path: Path,
) -> None:
    """Removing or adding owned jobs does not reconstruct any foreign cron bytes."""

    installer = SCRIPT_DIR / "unraid-install-user-scripts.sh"
    cron = tmp_path / "customSchedule.cron"
    managed = (
        "*/5 * * * * /usr/local/emhttp/plugins/user.scripts/startCustom.php "
        "/boot/config/plugins/user.scripts/scripts/little-orbit-pending/script "
        "> /dev/null 2>&1"
    ).encode()
    prefix = b"# foreign header\r\n0 3 * * * /foreign --literal='$value'\r\n"
    suffix = b"foreign-tail-without-newline"
    original = prefix + managed + b"\r\n" + suffix + b"\n" + managed
    expected_foreign = prefix + suffix + b"\n"
    cron.write_bytes(original)

    def call(function: str) -> subprocess.CompletedProcess[str]:
        return run_bash(
            f'source "$1"; {function} "$2"',
            installer.resolve().as_posix(),
            cron.resolve().as_posix(),
        )

    removed = call("remove_managed_cron_lines")
    assert removed.returncode == 0, removed.stderr
    assert cron.read_bytes() == expected_foreign

    cron.write_bytes(original)
    first_activation = call("activate_cron")
    assert first_activation.returncode == 0, first_activation.stderr
    activated = cron.read_bytes()
    assert activated.startswith(expected_foreign)
    assert activated.count(b"/scripts/little-orbit-") == 3
    second_activation = call("activate_cron")
    assert second_activation.returncode == 0, second_activation.stderr
    assert cron.read_bytes() == activated

    stale_variant = prefix + managed.replace(b"startCustom.php ", b"startCustom.php  ")
    cron.write_bytes(stale_variant)
    rejected = call("remove_managed_cron_lines")
    assert rejected.returncode == 78
    assert cron.read_bytes() == stale_variant
