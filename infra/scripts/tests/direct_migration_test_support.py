"""Shared fixtures for the focused direct-migration tests."""

from __future__ import annotations

import argparse
import importlib.util
from pathlib import Path
from typing import Any

import pytest

from infra.scripts.tests.migration_security_test_support import _reviewed_security


SCRIPT_DIR = Path(__file__).resolve().parents[1]


def load_script(name: str) -> Any:
    spec = importlib.util.spec_from_file_location(name.replace("-", "_"), SCRIPT_DIR / name)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


MODULE = load_script("direct_migration.py")
RESTORE = load_script("restore-attachment-backup.py")


def arguments(tmp_path: Path, direction: str = "forward") -> argparse.Namespace:
    identity, known_hosts, env_file, backup_identity = (
        tmp_path / name
        for name in (
            "migration-key",
            "known-hosts",
            "runtime.env",
            "backup-age-identity.txt",
        )
    )
    releases, rollback_root = tmp_path / "releases", tmp_path / "rollback-data"
    for path in (identity, known_hosts, env_file, backup_identity):
        path.write_text("fixture", encoding="utf-8")
    releases.mkdir()
    (releases / "little-orbit.apk").write_bytes(b"immutable-fixture")
    if direction == "rollback":
        rollback_root.mkdir()
    value = argparse.Namespace(
        direction=direction,
        local_host="192.168.50.182",
        unraid_host="192.168.50.14",
        unraid_user="root",
        unraid_port=23,
        ssh_identity=identity,
        known_hosts=known_hosts,
        backup_identity=backup_identity if direction == "forward" else None,
        unraid_stack=MODULE.UNRAID_STACK,
        local_env=env_file,
        local_release_root=releases,
        rollback_data_root=(
            rollback_root.resolve() if direction == "rollback" else None
        ),
        confirm=MODULE.CONFIRMATIONS[direction],
    )
    if direction == "rollback":
        value.rollback_root_guard = MODULE.safety.pin_rollback_root(
            value.rollback_data_root,
            require_empty=True,
        )
    return value


RECOVERY_CONFIRMATIONS = {
    "recover-forward": "recover-interrupted-forward-.14-state",
    "recover-rollback": "recover-interrupted-rollback-.182-state",
}


def recovery_arguments(tmp_path: Path, direction: str) -> argparse.Namespace:
    """Build valid path fixtures without weakening the recovery-only contract."""

    migration_direction = "forward" if direction == "recover-forward" else "rollback"
    value = arguments(tmp_path, migration_direction)
    value.direction = direction
    value.confirm = RECOVERY_CONFIRMATIONS[direction]
    value.backup_identity = None
    return value


def sample_inventory(head: str = "0031", queue: bool = False) -> object:
    tables = {
        "question_feedback": 7,
        "question_feedback_operations": 9,
    }
    if queue:
        tables["ai_work_queue"] = 0
    return MODULE.inventory.MigrationInventory(
        database={
            "tables": tables,
            "schema_heads": [head],
            "security": _reviewed_security(queue=queue),
        },
        attachments=MODULE.inventory.AttachmentInventory(2, 13, "0" * 64),
        releases={"little-orbit.apk": {"bytes": 21, "sha256": "1" * 64}},
    )


def source_attachment_mount() -> object:
    return MODULE.artifacts.AttachmentMount(
        "volume",
        "/var/lib/docker/volumes/little-orbit_attachment-data/_data",
        "little-orbit_attachment-data",
    )


def bypass_source_proofs(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        MODULE,
        "prove_source_attachment_mount",
        lambda *_args: source_attachment_mount(),
    )
    monkeypatch.setattr(
        MODULE,
        "prove_local_environment_provenance",
        lambda *_args: MODULE.safety.ProvenLocalSecrets(b"env", b"identity"),
    )
