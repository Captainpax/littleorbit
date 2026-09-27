"""Migration execution, failure, and evidence tests."""

from __future__ import annotations

import argparse
from pathlib import Path
import subprocess

import pytest

from infra.scripts.tests.direct_migration_test_support import (
    MODULE,
    arguments,
    bypass_source_proofs,
    sample_inventory,
    source_attachment_mount,
)


def test_failed_partial_stop_restarts_exact_original_writers(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    value = arguments(tmp_path)
    events: list[str] = []

    def run(_args: argparse.Namespace, location: str, *items: str, **_kwargs: object) -> str:
        if items[0] == "build":
            assert location == "unraid"
            assert items[1:] == MODULE.FORWARD_BUILD_SERVICES
            events.append("target-images-built")
            return ""
        if items[0] == "stop":
            events.append("stop-failed")
            raise subprocess.CalledProcessError(1, list(items))
        return ""

    monkeypatch.setattr(MODULE, "validate_arguments", lambda _args: None)
    monkeypatch.setattr(MODULE, "running_writers", lambda *_args: ("gateway", "api"))
    bypass_source_proofs(monkeypatch)
    monkeypatch.setattr(MODULE, "assert_local_release_mount", lambda _args: None)
    guard = MODULE.target_state.TargetGuard("fixture")
    monkeypatch.setattr(MODULE.target_state, "new_guard", lambda: guard)
    monkeypatch.setattr(MODULE.target_state, "begin_fresh_target", lambda *_args: None)
    monkeypatch.setattr(MODULE, "transfer_forward_secrets", lambda *_args: None)
    monkeypatch.setattr(MODULE, "prepare_database", lambda *_args: None)
    monkeypatch.setattr(
        MODULE.target_state, "assert_only_postgres_running", lambda *_args: None,
    )
    monkeypatch.setattr(
        MODULE, "create_remote_staging",
        lambda _args, kind, _owner: f"/stage/{kind}",
    )
    monkeypatch.setattr(MODULE, "run_stack", run)
    monkeypatch.setattr(
        MODULE.target_state, "recover_failed_target",
        lambda *_args: events.append("target-erased") or ("preparing", "erased", True),
    )
    monkeypatch.setattr(
        MODULE, "restart_source_writers",
        lambda *_args: events.append("source-healthy"),
    )
    class Exclusion:
        def assert_held(self) -> None:
            pass

    with pytest.raises(MODULE.MigrationFailure) as raised:
        MODULE.execute_migration(value, Exclusion())
    assert events == [
        "target-images-built", "stop-failed", "target-erased", "source-healthy",
    ]
    assert raised.value.recovery["source_writers"] == "healthy"


def test_env_and_identity_proof_fail_before_any_target_mutation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    value = arguments(tmp_path)
    mutated: list[bool] = []
    monkeypatch.setattr(MODULE, "validate_arguments", lambda _args: None)
    monkeypatch.setattr(MODULE, "running_writers", lambda *_args: MODULE.WRITER_SERVICES)
    monkeypatch.setattr(
        MODULE, "prove_source_attachment_mount", lambda *_args: source_attachment_mount(),
    )
    monkeypatch.setattr(
        MODULE, "prove_local_environment_provenance",
        lambda *_args: (_ for _ in ()).throw(RuntimeError("provenance rejected")),
    )
    monkeypatch.setattr(
        MODULE.target_state, "begin_fresh_target",
        lambda *_args: mutated.append(True),
    )
    with pytest.raises(MODULE.MigrationFailure) as raised:
        MODULE.execute_migration(value)
    assert mutated == []
    assert "provenance rejected" in str(raised.value.__cause__)


def test_active_ai_aborts_before_stream_and_restarts_unraid(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    value = arguments(tmp_path, "rollback")
    value.migration_lock_token = "a" * 64

    def run(_args: argparse.Namespace, location: str, *items: str, **kwargs: object) -> str:
        if kwargs.get("capture"):
            return '{"ai_runs_running":1,"admin_ai_jobs_running":0}'
        return ""

    monkeypatch.setattr(MODULE, "validate_arguments", lambda _args: None)
    monkeypatch.setattr(MODULE, "running_writers", lambda *_args: ("api",))
    bypass_source_proofs(monkeypatch)
    monkeypatch.setattr(
        MODULE, "prepare_rollback",
        lambda _args: (value.rollback_data_root / ".a", value.rollback_data_root / ".r"),
    )
    monkeypatch.setattr(MODULE, "run_stack", run)
    monkeypatch.setattr(MODULE, "assert_local_production_stopped", lambda _args: None)
    monkeypatch.setattr(MODULE, "assert_fresh_rollback_project", lambda _args: None)
    guard = MODULE.target_state.TargetGuard("1" * 32)
    monkeypatch.setattr(MODULE.target_state, "new_guard", lambda: guard)
    monkeypatch.setattr(MODULE.target_state, "begin_rollback", lambda *_args: None)
    monkeypatch.setattr(
        MODULE.target_state, "recover_failed_rollback",
        lambda *_args: ("rollback-preparing", "cleanup-required", True),
    )
    monkeypatch.setattr(
        MODULE.target_state, "complete_failed_rollback", lambda *_args: None,
    )
    monkeypatch.setattr(
        MODULE.target_state, "begin_rollback", lambda *_args: None, raising=False,
    )
    monkeypatch.setattr(MODULE, "assert_no_unexpected_database_sessions", lambda *_args: None)
    monkeypatch.setattr(MODULE, "clean_rollback_destination", lambda _args: None)
    restarted: list[tuple[str, ...]] = []
    monkeypatch.setattr(
        MODULE, "restart_source_writers",
        lambda _args, _source, writers: restarted.append(writers),
    )
    class Exclusion:
        def assert_held(self) -> None:
            pass

    with pytest.raises(MODULE.MigrationFailure) as raised:
        MODULE.execute_migration(value, Exclusion())
    assert isinstance(raised.value.__cause__, RuntimeError)
    assert "active AI work" in str(raised.value.__cause__)
    assert restarted == [("api",)]


def test_foreign_rollback_destination_is_never_cleaned(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    value = arguments(tmp_path, "rollback")
    cleaned: list[bool] = []
    monkeypatch.setattr(MODULE, "validate_arguments", lambda _args: None)
    monkeypatch.setattr(MODULE, "running_writers", lambda *_args: MODULE.WRITER_SERVICES)
    bypass_source_proofs(monkeypatch)
    monkeypatch.setattr(MODULE, "assert_local_production_stopped", lambda _args: None)
    monkeypatch.setattr(
        MODULE, "assert_fresh_rollback_project",
        lambda _args: (_ for _ in ()).throw(RuntimeError("foreign destination")),
    )
    monkeypatch.setattr(MODULE, "clean_rollback_destination", lambda _args: cleaned.append(True))
    with pytest.raises(MODULE.MigrationFailure) as raised:
        MODULE.execute_migration(value)
    assert cleaned == []
    assert raised.value.recovery["target_cleanup"] == "not-needed"


def test_success_evidence_has_explicit_pre_and_post_inventory(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    value = arguments(tmp_path)
    expected = sample_inventory()
    target = sample_inventory("0032", True)
    monkeypatch.setattr(MODULE, "validate_arguments", lambda _args: None)
    monkeypatch.setattr(MODULE, "running_writers", lambda *_args: MODULE.WRITER_SERVICES)
    bypass_source_proofs(monkeypatch)
    monkeypatch.setattr(MODULE, "assert_local_release_mount", lambda _args: None)
    guard = MODULE.target_state.TargetGuard("fixture")
    monkeypatch.setattr(MODULE.target_state, "new_guard", lambda: guard)
    monkeypatch.setattr(MODULE.target_state, "begin_fresh_target", lambda *_args: None)
    monkeypatch.setattr(
        MODULE, "prepare_forward",
        lambda *_args: ("/stage/attachments", "/stage/releases"),
    )

    def run(_args: argparse.Namespace, _location: str, *_items: str, **kwargs: object) -> str:
        return '{"ai_runs_running":0,"admin_ai_jobs_running":0}' if kwargs.get("capture") else ""

    monkeypatch.setattr(MODULE, "run_stack", run)
    sessions: list[str] = []
    sources: list[str] = []
    monkeypatch.setattr(
        MODULE, "assert_no_unexpected_database_sessions",
        lambda _args, location: sessions.append(location),
    )
    monkeypatch.setattr(
        MODULE, "source_inventory",
        lambda _args, location, _mount: sources.append(location) or expected,
    )
    monkeypatch.setattr(MODULE, "stream_database", lambda *_args: None)
    monkeypatch.setattr(MODULE, "stream_attachments", lambda *_args: None)
    monkeypatch.setattr(MODULE, "stream_forward_releases", lambda *_args: None)
    monkeypatch.setattr(MODULE, "seal_staging", lambda *_args: None)
    monkeypatch.setattr(MODULE, "staged_inventory", lambda *_args: target)
    monkeypatch.setattr(MODULE, "promote_remote", lambda *_args: None)
    evidence = MODULE.execute_migration(value)
    assert evidence["destination"]["inventory"]["database"]["schema_heads"] == ["0032"]
    assert evidence["source"]["inventory"]["database"]["tables"] == {
        "question_feedback": 7,
        "question_feedback_operations": 9,
    }
    assert evidence["inventories_match"] is True
    assert sessions == ["local-production", "local-production"]
    assert sources == ["local-production", "local-production"]


def test_committed_target_never_restarts_stale_source(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    value = arguments(tmp_path)
    guard = MODULE.target_state.TargetGuard("fixture")
    monkeypatch.setattr(
        MODULE.target_state, "recover_failed_target",
        lambda *_args: ("committed", "preserved", False),
    )
    monkeypatch.setattr(
        MODULE, "restart_source_writers",
        lambda *_args: pytest.fail("committed source must remain frozen"),
    )
    observed = MODULE._recover_failure(
        value, "local-production", MODULE.WRITER_SERVICES, guard, True, True,
    )
    assert observed == {
        "target_phase": "committed", "target_cleanup": "preserved",
        "source_writers": "frozen",
    }
