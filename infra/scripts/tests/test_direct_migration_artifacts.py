"""Target, database, attachment, and release migration tests."""

from __future__ import annotations

from dataclasses import asdict
import json
from pathlib import Path
import subprocess
import sys

import pytest

from infra.scripts.tests.direct_migration_test_support import (
    MODULE,
    arguments,
    source_attachment_mount,
)


def test_target_guard_proves_exact_btrfs_roots_and_no_containers() -> None:
    commands: list[list[str]] = []
    guard = MODULE.target_state.TargetGuard("fixture")
    MODULE.target_state.begin_fresh_target(
        lambda command, **_kwargs: commands.append(command) or "", ["ssh"],
        MODULE.remote_shell, guard,
    )
    script = commands[0][-1]
    assert "findmnt" in script and "btrfs balance status" in script
    assert MODULE.target_state.POSTGRES_ROOT in script
    assert "docker ps -aq --filter" in script and "docker inspect --format" in script
    assert guard.preparing_value in script


def test_target_postgres_layout_and_only_service_are_proven() -> None:
    remote: list[str] = []

    def stack(_args: object, _location: str, *values: str, **_kwargs: object) -> str:
        if values[:3] == ("ps", "--services", "--status"):
            return "postgres"
        if values[:2] == ("ps", "-q"):
            return "a" * 64
        return ""

    MODULE.target_state.assert_only_postgres_running(
        lambda command, **_kwargs: remote.append(command[-1]) or "", ["ssh"],
        MODULE.remote_shell, stack, object(),
    )
    assert MODULE.target_state.POSTGRES_ROOT in remote[0]
    assert "/var/lib/postgresql/data" in remote[0]


def test_release_inventory_is_relative_and_includes_size(tmp_path: Path) -> None:
    root = tmp_path / "releases"
    nested = root / "android"
    nested.mkdir(parents=True)
    (nested / "app.apk").write_bytes(b"immutable")
    assert MODULE.inventory.release_inventory(root) == {
        "android/app.apk": {
            "bytes": 9,
            "sha256": "3e58bada6a180c0d7f817bdae51fba96a461575b309bfbc17a6918d20c6617c7",
        }
    }


def test_attachment_inventory_exposes_no_paths(tmp_path: Path) -> None:
    root = tmp_path / "attachments"
    (root / "private").mkdir(parents=True)
    (root / "private" / "secret-name.jpg").write_bytes(b"private")
    observed = asdict(MODULE.inventory.attachment_inventory(root))
    assert observed["file_count"] == 1
    assert observed["total_bytes"] == 7
    assert "secret-name" not in json.dumps(observed)


def test_inventory_one_shot_bundles_its_security_dependency(tmp_path: Path) -> None:
    root = tmp_path / "attachments"
    root.mkdir()
    (root / "fixture.bin").write_bytes(b"fixture")
    result = subprocess.run(
        [
            sys.executable, "-I", "-c", MODULE.artifacts._inventory_program(),
            "attachments", str(root),
        ],
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    assert json.loads(result.stdout) == asdict(
        MODULE.inventory.attachment_inventory(root)
    )


def test_attachment_reader_is_bound_to_the_exact_live_writer_mount(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    payloads = {
        "api": json.dumps([{
            "Type": "volume", "Source": "/docker/source", "Name": "exact-volume",
            "Destination": MODULE.ATTACHMENT_CONTAINER_ROOT, "RW": True,
        }]),
        "worker": json.dumps([{
            "Type": "volume", "Source": "/docker/source", "Name": "exact-volume",
            "Destination": MODULE.ATTACHMENT_CONTAINER_ROOT, "RW": True,
        }]),
        "media-worker": json.dumps([{
            "Type": "volume", "Source": "/docker/source", "Name": "exact-volume",
            "Destination": MODULE.ATTACHMENT_CONTAINER_ROOT, "RW": True,
        }]),
    }
    monkeypatch.setattr(
        MODULE.artifacts, "_container_id",
        lambda _runtime, _args, _location, service: service,
    )
    monkeypatch.setattr(
        MODULE.artifacts, "_mounts_json",
        lambda _runtime, _args, _location, container: payloads[container],
    )
    mount = MODULE.artifacts.prove_source_attachment_mount(
        object(), object(), "local-production",
    )
    assert mount.compose_source == "exact-volume"
    payloads["media-worker"] = payloads["media-worker"].replace(
        "exact-volume", "wrong-volume",
    )
    with pytest.raises(RuntimeError, match="one exact mount"):
        MODULE.artifacts.prove_source_attachment_mount(
            object(), object(), "local-production",
        )


def test_unraid_attachment_source_must_be_the_fixed_live_bind(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    payload = json.dumps([{
        "Type": "bind", "Source": "/mnt/cache/not-the-live-root", "Name": "",
        "Destination": MODULE.ATTACHMENT_CONTAINER_ROOT, "RW": True,
    }])
    monkeypatch.setattr(
        MODULE.artifacts, "_container_id", lambda *_args: "a" * 64,
    )
    monkeypatch.setattr(MODULE.artifacts, "_mounts_json", lambda *_args: payload)
    with pytest.raises(RuntimeError, match="fixed live root"):
        MODULE.artifacts.prove_source_attachment_mount(object(), object(), "unraid")


def test_open_secret_snapshot_rejects_a_later_edit(tmp_path: Path) -> None:
    secret = tmp_path / "runtime.env"
    secret.write_bytes(b"SESSION_SECRET=first\n")
    with secret.open("rb") as handle:
        snapshot, identity = MODULE.safety.capture_open_file(handle, secret)
        secret.write_bytes(b"SESSION_SECRET=other\n")
        with pytest.raises(RuntimeError, match="changed during preflight"):
            MODULE.safety.prove_open_file_unchanged(
                handle, secret, snapshot, identity,
            )


def test_attachment_restore_uses_sibling_stage_and_application_owner(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    captured: tuple[list[str], list[str]] | None = None

    def capture(source: list[str], destination: list[str], **_kwargs: object) -> None:
        nonlocal captured
        captured = (source, destination)

    monkeypatch.setattr(MODULE, "pipe_commands", capture)
    stage = "/mnt/cache/little-orbit-live/.attachments-migration-fixture"
    value = arguments(tmp_path)
    value.migration_lock_token = "d" * 64
    mount = source_attachment_mount()
    MODULE.stream_attachments(
        value, "local-production", "unraid", stage, mount,
    )
    assert captured is not None
    destination = captured[1][-1]
    assert "backup-attachment-reader" in captured[0]
    assert any(
        item.startswith("little-orbit_attachment-data:") for item in captured[0]
    )
    assert "--user 65532:65532" in destination
    assert f"{stage}:{MODULE.ATTACHMENT_CONTAINER_ROOT}" in destination
    assert "LITTLE_ORBIT_ATTACHMENT_RESTORE_MODE=stage" in destination


@pytest.mark.parametrize(
    ("source", "destination"),
    [("local-production", "unraid"), ("unraid", "local-rollback")],
)
def test_database_restore_is_single_transaction_and_exit_on_error(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    source: str,
    destination: str,
) -> None:
    value = arguments(tmp_path, "rollback" if source == "unraid" else "forward")
    captured: tuple[list[str], list[str]] | None = None
    stack_calls: list[tuple[str, ...]] = []

    def capture(first: list[str], second: list[str], **_kwargs: object) -> None:
        nonlocal captured
        captured = (first, second)

    monkeypatch.setattr(MODULE, "pipe_commands", capture)
    monkeypatch.setattr(MODULE, "run_stack", lambda _args, _location, *items, **_kwargs: stack_calls.append(items) or "")
    MODULE.stream_database(value, source, destination)
    assert captured is not None
    assert all(value in captured[1][-1] for value in ("--single-transaction", "--exit-on-error")) and "--format=custom" in captured[0][-1]
    assert any(call[-1] == "migrate" for call in stack_calls) and any(call[-1] == "database-grants" for call in stack_calls)


def test_active_ai_guard_reports_only_counts() -> None:
    observed = MODULE.inventory.parse_active_ai(
        '{"ai_runs_running":2,"admin_ai_jobs_running":1}'
    )
    assert observed == {"ai_runs_running": 2, "admin_ai_jobs_running": 1}
    assert "summary_json" not in MODULE.inventory.ACTIVE_AI_SQL and "result_json" not in MODULE.inventory.ACTIVE_AI_SQL
