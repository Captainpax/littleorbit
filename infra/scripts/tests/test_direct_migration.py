"""Focused safety tests for bidirectional direct migration."""

from __future__ import annotations

import argparse
from dataclasses import asdict
import importlib.util
import io
import json
from pathlib import Path
import shutil
import shlex
import subprocess
import tarfile
from typing import Any

import pytest

SCRIPT_DIR = Path(__file__).resolve().parents[1]


def load_script(name: str) -> Any:
    """Load one hyphenated or standalone infrastructure script."""

    spec = importlib.util.spec_from_file_location(name.replace("-", "_"), SCRIPT_DIR / name)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


MODULE = load_script("direct_migration.py")
RESTORE = load_script("restore-attachment-backup.py")


def arguments(tmp_path: Path, direction: str = "forward") -> argparse.Namespace:
    """Return a complete, non-secret argument set for one direction."""

    identity = tmp_path / "migration-key"
    known_hosts = tmp_path / "known-hosts"
    env_file = tmp_path / "runtime.env"
    backup_identity = tmp_path / "backup-age-identity.txt"
    releases = tmp_path / "releases"
    rollback_root = tmp_path / "rollback-data"
    for path in (identity, known_hosts, env_file, backup_identity):
        path.write_text("fixture", encoding="utf-8")
    releases.mkdir()
    if direction == "rollback":
        rollback_root.mkdir()
    return argparse.Namespace(
        direction=direction,
        local_host="192.168.50.182",
        unraid_host="192.168.50.14",
        unraid_user="root",
        unraid_port=23,
        ssh_identity=identity,
        known_hosts=known_hosts,
        backup_identity=backup_identity if direction == "forward" else None,
        unraid_stack="/fixed/unraid-stack.sh",
        local_env=env_file,
        local_release_root=releases,
        rollback_data_root=rollback_root.resolve() if direction == "rollback" else None,
        confirm=MODULE.CONFIRMATIONS[direction],
    )


def sample_inventory() -> object:
    """Return content-free evidence with privacy-sensitive tables represented."""

    return MODULE.inventory.MigrationInventory(
        database={
            "tables": {"question_feedback": 7, "question_feedback_operations": 9},
            "schema_heads": ["0032_gpu_work_queue"],
        },
        attachments=MODULE.inventory.AttachmentInventory(2, 13, "0" * 64),
        releases={"little-orbit.apk": {"bytes": 21, "sha256": "1" * 64}},
    )


def test_validation_rejects_any_other_host(tmp_path: Path) -> None:
    """A typo cannot redirect the complete private stream elsewhere."""

    value = arguments(tmp_path)
    value.unraid_host = "192.168.50.15"
    with pytest.raises(ValueError, match="hosts must be"):
        MODULE.validate_arguments(value)


def test_runtime_route_must_originate_on_fixed_legacy_host() -> None:
    """A copied command cannot stream production data from another machine."""

    MODULE.safety.require_routed_local_host(
        "192.168.50.182", "192.168.50.14", 23, observed="192.168.50.182"
    )
    with pytest.raises(ValueError, match="must run on 192.168.50.182"):
        MODULE.safety.require_routed_local_host(
            "192.168.50.182", "192.168.50.14", 23, observed="192.168.50.99"
        )


def test_direction_requires_unmistakable_confirmation(tmp_path: Path) -> None:
    """Forward confirmation cannot authorize a post-write rollback."""

    value = arguments(tmp_path, "rollback")
    value.confirm = MODULE.CONFIRMATIONS["forward"]
    with pytest.raises(ValueError, match="confirmation"):
        MODULE.validate_arguments(value)


def test_rollback_rejects_secret_transfer_and_nonempty_root(tmp_path: Path) -> None:
    """Rollback neither overwrites `.182` secrets nor reuses prior data."""

    value = arguments(tmp_path, "rollback")
    value.backup_identity = tmp_path / "backup-age-identity.txt"
    with pytest.raises(ValueError, match="never transfers"):
        MODULE.validate_arguments(value)
    value.backup_identity = None
    (value.rollback_data_root / "old").write_text("stale", encoding="utf-8")
    with pytest.raises(ValueError, match="must be empty"):
        MODULE.validate_arguments(value)


def test_cli_has_no_archive_output_option() -> None:
    """The migration helper cannot persist a complete database dump."""

    destinations = {action.dest for action in MODULE.parser()._actions}
    assert "direction" in destinations
    assert "output" not in destinations
    assert "archive" not in destinations


def test_compound_remote_commands_use_fail_fast_shell() -> None:
    """A failed guard cannot be hidden by a later successful command."""

    assert shlex.split(MODULE.remote_shell("false; true")) == ["sh", "-ec", "false; true"]


def test_unraid_launcher_keeps_base_compose_path_semantics() -> None:
    """Build contexts and bind mounts stay relative to the base file in infra/."""

    launcher = (SCRIPT_DIR / "unraid-stack.sh").read_text(encoding="utf-8")
    assert '--project-directory "${DEPLOY_ROOT}/infra"' in launcher


def test_forward_runtime_override_uses_exact_gpu_lock_inode(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The transferred runtime env points at the stable lock file, not its directory."""

    captured: list[tuple[Path, str, bytes]] = []

    def capture(
        _args: argparse.Namespace, source: Path, target: str, suffix: bytes = b""
    ) -> None:
        captured.append((source, target, suffix))

    monkeypatch.setattr(MODULE, "stream_secret", capture)
    MODULE.transfer_forward_secrets(arguments(tmp_path))
    runtime_suffix = captured[0][2]
    assert b"GPU_LOCK_HOST_PATH=/mnt/cache/gpu-coordinator/gpu.lock\n" in runtime_suffix
    assert captured[1][1] == MODULE.UNRAID_BACKUP_IDENTITY


def test_release_inventory_is_relative_and_includes_size(tmp_path: Path) -> None:
    """Release evidence contains public relative names, sizes, and hashes."""

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
    """Attachment evidence hashes paths internally but reports only aggregates."""

    root = tmp_path / "attachments"
    (root / "private").mkdir(parents=True)
    (root / "private" / "secret-name.jpg").write_bytes(b"private")
    observed = asdict(MODULE.inventory.attachment_inventory(root))
    assert observed["file_count"] == 1
    assert observed["total_bytes"] == 7
    assert "secret-name" not in json.dumps(observed)


def test_attachment_restore_uses_sibling_stage_and_application_owner(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Forward restore never swaps children inside the mounted live root."""

    captured: tuple[list[str], list[str]] | None = None

    def capture(source: list[str], destination: list[str], **_kwargs: object) -> None:
        nonlocal captured
        captured = (source, destination)

    monkeypatch.setattr(MODULE, "pipe_commands", capture)
    stage = "/mnt/cache/little-orbit-live/.attachments-migration-fixture"
    MODULE.stream_attachments(arguments(tmp_path), "local-production", "unraid", stage)
    assert captured is not None
    destination = captured[1][-1]
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
    """Neither direction can leave a partially restored database."""

    value = arguments(tmp_path, "rollback" if source == "unraid" else "forward")
    captured: tuple[list[str], list[str]] | None = None

    def capture(first: list[str], second: list[str], **_kwargs: object) -> None:
        nonlocal captured
        captured = (first, second)

    monkeypatch.setattr(MODULE, "pipe_commands", capture)
    monkeypatch.setattr(MODULE, "run_stack", lambda *_args, **_kwargs: "")
    MODULE.stream_database(value, source, destination)
    assert captured is not None
    assert "--single-transaction" in captured[1][-1]
    assert "--exit-on-error" in captured[1][-1]
    assert "--format=custom" in captured[0][-1]


def test_active_ai_guard_reports_only_counts() -> None:
    """AI freeze evidence contains statuses/counts, never prompts or results."""

    observed = MODULE.inventory.parse_active_ai(
        '{"ai_runs_running":2,"admin_ai_jobs_running":1}'
    )
    assert observed == {"ai_runs_running": 2, "admin_ai_jobs_running": 1}
    assert "summary_json" not in MODULE.inventory.ACTIVE_AI_SQL
    assert "result_json" not in MODULE.inventory.ACTIVE_AI_SQL


def test_failed_partial_stop_restarts_exact_original_writers(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A partially successful Compose stop cannot strand source writers."""

    value = arguments(tmp_path)
    calls: list[tuple[str, tuple[str, ...]]] = []

    def run(_args: argparse.Namespace, location: str, *items: str, **_kwargs: object) -> str:
        calls.append((location, items))
        if items[0] == "stop":
            raise subprocess.CalledProcessError(1, list(items))
        return ""

    monkeypatch.setattr(MODULE, "validate_arguments", lambda _args: None)
    monkeypatch.setattr(
        MODULE, "prepare_forward",
        lambda _args: ("/stage/attachments", "/stage/releases", ("gateway", "api")),
    )
    monkeypatch.setattr(MODULE, "run_stack", run)
    monkeypatch.setattr(MODULE, "remove_remote_staging", lambda *_args: None)
    with pytest.raises(subprocess.CalledProcessError):
        MODULE.execute_migration(value)
    assert ("local-production", ("start", "gateway", "api")) in calls


def test_active_ai_aborts_before_stream_and_restarts_unraid(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Post-write rollback cannot freeze a fresh AI claim into restored state."""

    value = arguments(tmp_path, "rollback")
    calls: list[tuple[str, tuple[str, ...]]] = []

    def run(_args: argparse.Namespace, location: str, *items: str, **kwargs: object) -> str:
        calls.append((location, items))
        if kwargs.get("capture"):
            return '{"ai_runs_running":1,"admin_ai_jobs_running":0}'
        return ""

    monkeypatch.setattr(MODULE, "validate_arguments", lambda _args: None)
    monkeypatch.setattr(
        MODULE, "prepare_rollback",
        lambda _args: (value.rollback_data_root / ".a", value.rollback_data_root / ".r", ("api",)),
    )
    monkeypatch.setattr(MODULE, "run_stack", run)
    monkeypatch.setattr(MODULE, "clean_rollback_destination", lambda _args: None)
    with pytest.raises(RuntimeError, match="active AI work"):
        MODULE.execute_migration(value)
    assert ("unraid", ("start", "api")) in calls


def test_success_evidence_has_explicit_pre_and_post_inventory(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """Success emits exact source/destination equality evidence."""

    value = arguments(tmp_path)
    expected = sample_inventory()
    monkeypatch.setattr(MODULE, "validate_arguments", lambda _args: None)
    monkeypatch.setattr(
        MODULE, "prepare_forward",
        lambda _args: ("/stage/attachments", "/stage/releases", MODULE.WRITER_SERVICES),
    )

    def run(_args: argparse.Namespace, _location: str, *_items: str, **kwargs: object) -> str:
        return '{"ai_runs_running":0,"admin_ai_jobs_running":0}' if kwargs.get("capture") else ""

    monkeypatch.setattr(MODULE, "run_stack", run)
    monkeypatch.setattr(MODULE, "source_inventory", lambda *_args: expected)
    monkeypatch.setattr(MODULE, "stream_database", lambda *_args: None)
    monkeypatch.setattr(MODULE, "stream_attachments", lambda *_args: None)
    monkeypatch.setattr(MODULE, "stream_forward_releases", lambda *_args: None)
    monkeypatch.setattr(MODULE, "seal_staging", lambda *_args: None)
    monkeypatch.setattr(MODULE, "staged_inventory", lambda *_args: expected)
    monkeypatch.setattr(MODULE, "promote_remote", lambda *_args: None)
    MODULE.execute_migration(value)
    evidence = json.loads(capsys.readouterr().out)
    assert evidence["source"]["inventory"] == evidence["destination"]["inventory"]
    assert evidence["source"]["inventory"]["database"]["tables"] == {
        "question_feedback": 7,
        "question_feedback_operations": 9,
    }
    assert evidence["inventories_match"] is True


def test_local_pair_promotion_rolls_back_first_rename_on_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A second-tree failure restores the first whole sibling tree."""

    value = arguments(tmp_path, "rollback")
    attachments = value.rollback_data_root / ".attachments-migration-test"
    releases = value.rollback_data_root / ".releases-migration-test"
    attachments.mkdir()
    releases.mkdir()
    (attachments / "one").write_bytes(b"one")
    real_replace = MODULE.os.replace

    def replace(source: Path, destination: Path) -> None:
        if Path(destination).name == "releases":
            raise OSError("injected failure")
        real_replace(source, destination)

    monkeypatch.setattr(MODULE.os, "replace", replace)
    with pytest.raises(OSError, match="injected"):
        MODULE.promote_local(value, attachments, releases)
    assert attachments.is_dir()
    assert not (value.rollback_data_root / "attachments").exists()


def test_rollback_cleanup_refuses_unexpected_paths(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Failure cleanup cannot delete a file added outside migration staging."""

    value = arguments(tmp_path, "rollback")
    unexpected = value.rollback_data_root / "operator-note.txt"
    unexpected.write_text("preserve", encoding="utf-8")
    monkeypatch.setattr(MODULE, "run_stack", lambda *_args, **_kwargs: "")
    with pytest.raises(RuntimeError, match="unexpected path"):
        MODULE.clean_rollback_destination(value)
    assert unexpected.read_text(encoding="utf-8") == "preserve"


def test_stage_restore_populates_only_disposable_root(tmp_path: Path) -> None:
    """Verified attachment children are never swapped through a live directory."""

    root = tmp_path / "sibling-stage"
    staging = root / ".restore-new-fixture"
    (staging / "nested").mkdir(parents=True)
    (staging / "nested" / "file").write_bytes(b"bytes")
    RESTORE.populate_empty_staging(staging, root)
    assert (root / "nested" / "file").read_bytes() == b"bytes"
    assert not staging.exists()


def test_release_extractor_rejects_links(tmp_path: Path) -> None:
    """Reverse streaming cannot materialize symlinks from Unraid."""

    stream = io.BytesIO()
    with tarfile.open(fileobj=stream, mode="w") as archive:
        member = tarfile.TarInfo("unsafe-link")
        member.type = tarfile.SYMTYPE
        member.linkname = "elsewhere"
        archive.addfile(member)
    stream.seek(0)
    with pytest.raises(RuntimeError, match="non-regular"):
        MODULE.inventory.extract_release_archive(stream, tmp_path)


def test_recovery_compose_uses_explicit_bind_root_and_loopback_gateway() -> None:
    """The rollback project cannot reuse production storage or publish broadly."""

    override = (SCRIPT_DIR.parent / "compose.rollback.yaml").read_text(encoding="utf-8")
    assert "${ROLLBACK_DATA_ROOT:?set ROLLBACK_DATA_ROOT}/attachments" in override
    assert "${ROLLBACK_DATA_ROOT:?set ROLLBACK_DATA_ROOT}/releases" in override
    assert "127.0.0.1" in override


@pytest.mark.parametrize(
    "name",
    [
        "unraid-stack.sh",
        "unraid-bootstrap.sh",
        "unraid-firewall.sh",
        "unraid-user-script.sh",
        "unraid-backup.sh",
        "unraid-restore-drill.sh",
        "unraid-operations.sh",
        "unraid-install-user-scripts.sh",
    ],
)
def test_unraid_shell_entrypoints_parse(name: str) -> None:
    """Every checked-in Unraid entry point is valid Bash."""

    git_bash = Path("C:/Program Files/Git/bin/bash.exe")
    executable = str(git_bash) if git_bash.is_file() else shutil.which("bash")
    if executable is None:
        pytest.skip("Bash is unavailable")
    subprocess.run([executable, "-n", str(SCRIPT_DIR / name)], check=True)
