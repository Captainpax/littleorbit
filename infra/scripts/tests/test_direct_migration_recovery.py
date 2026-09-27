"""Crash-recovery journal and restart-contract migration tests."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import pytest

from infra.scripts.tests.direct_migration_test_support import (
    MODULE,
    arguments,
    bypass_source_proofs,
    recovery_arguments,
)


def test_recovery_forward_keeps_restart_journal_until_exact_restart_is_healthy(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    value = recovery_arguments(tmp_path, "recover-forward")
    value.migration_lock_token = "a" * 64
    events: list[str] = []

    class Exclusion:
        def assert_held(self) -> None:
            events.append("lock-held")

    def recover(*_args: object) -> tuple[str, str]:
        events.append("remote-forward-cleaned")
        return "forward-cleaned", "restart-required"

    def restart(
        _args: argparse.Namespace, source: str, writers: tuple[str, ...],
    ) -> None:
        assert source == "local-production"
        assert writers == MODULE.WRITER_SERVICES
        events.append("legacy-writers-healthy")

    monkeypatch.setattr(MODULE, "validate_arguments", lambda _args: None)
    monkeypatch.setattr(
        MODULE.target_state, "recover_interrupted_forward", recover, raising=False,
    )
    monkeypatch.setattr(
        MODULE.target_state, "complete_interrupted_forward",
        lambda *_args: events.append("remote-recovery-complete"),
        raising=False,
    )
    monkeypatch.setattr(MODULE, "restart_source_writers", restart)
    evidence = MODULE.execute_recovery(value, Exclusion())
    assert events == [
        "lock-held", "remote-forward-cleaned", "lock-held",
        "legacy-writers-healthy", "lock-held", "remote-recovery-complete",
    ]
    encoded = json.dumps(evidence, sort_keys=True)
    assert value.migration_lock_token not in encoded
    assert all(
        item in encoded for item in ("forward-cleaned", "restart-required", "healthy")
    )


def test_recovery_forward_restart_failure_preserves_restart_required_journal(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    value = recovery_arguments(tmp_path, "recover-forward")
    completed: list[bool] = []

    class Exclusion:
        def assert_held(self) -> None:
            pass

    monkeypatch.setattr(MODULE, "validate_arguments", lambda _args: None)
    monkeypatch.setattr(
        MODULE.target_state, "recover_interrupted_forward",
        lambda *_args: ("forward-cleaned", "restart-required"),
        raising=False,
    )
    monkeypatch.setattr(
        MODULE.target_state, "complete_interrupted_forward",
        lambda *_args: completed.append(True),
        raising=False,
    )
    monkeypatch.setattr(
        MODULE, "restart_source_writers",
        lambda *_args: (_ for _ in ()).throw(RuntimeError("restart failed")),
    )
    with pytest.raises(RuntimeError, match="restart failed"):
        MODULE.execute_recovery(value, Exclusion())
    assert completed == []


@pytest.mark.parametrize(
    ("phase", "cleanup"),
    [("committed", "preserved"), ("absent", "not-needed")],
)
def test_recovery_forward_preserves_committed_and_noops_when_absent(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
    phase: str, cleanup: str,
) -> None:
    value = recovery_arguments(tmp_path, "recover-forward")
    events: list[str] = []

    class Exclusion:
        def assert_held(self) -> None:
            events.append("lock-held")

    monkeypatch.setattr(MODULE, "validate_arguments", lambda _args: None)
    monkeypatch.setattr(
        MODULE.target_state, "recover_interrupted_forward",
        lambda *_args: events.append("phase-read") or (phase, cleanup),
        raising=False,
    )
    monkeypatch.setattr(
        MODULE, "restart_source_writers",
        lambda *_args: pytest.fail("a committed or absent target must not restart .182"),
    )
    monkeypatch.setattr(
        MODULE.target_state, "complete_interrupted_forward",
        lambda *_args: pytest.fail("a committed or absent target has no restart journal"),
        raising=False,
    )
    evidence = MODULE.execute_recovery(value, Exclusion())
    assert events == ["lock-held", "phase-read"]
    encoded = json.dumps(evidence, sort_keys=True)
    assert phase in encoded and cleanup in encoded
    assert "healthy" not in encoded


@pytest.mark.parametrize(
    "outcome",
    [
        "foreign:" + "1" * 32,
        "preparing:short",
        "preparing:" + "1" * 32 + ":erased",
        "committed:" + "z" * 32,
        "forward-cleaned:" + "1" * 32,
    ],
)
def test_interrupted_forward_helper_refuses_malformed_or_foreign_outcomes(
    outcome: str,
) -> None:
    def run(_command: list[str], **_kwargs: object) -> str:
        return outcome

    with pytest.raises(RuntimeError, match="invalid|refus|marker|outcome"):
        MODULE.target_state.recover_interrupted_forward(
            run, ["ssh"], lambda script: script,
        )


def test_interrupted_forward_helper_validates_marker_without_returning_guard() -> None:
    commands: list[list[str]] = []

    def run(command: list[str], **_kwargs: object) -> str:
        commands.append(command)
        return "absent"

    assert MODULE.target_state.recover_interrupted_forward(
        run, ["ssh"], lambda script: script,
    ) == ("absent", "not-needed")
    script = commands[0][-1]
    assert MODULE.target_state.STATE_PATH in script
    assert "test ! -L" in script
    assert "regular file:0:0:600:1" in script
    assert "[0-9a-f]{32}" in script
    assert all(
        value in script for value in ("preparing:", "committed:", "forward-cleaned:")
    )
    assert "restart-required" in script
    assert "exit 78" in script


def test_recovery_forward_refusal_never_restarts_legacy_writers(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    value = recovery_arguments(tmp_path, "recover-forward")

    class Exclusion:
        def assert_held(self) -> None:
            pass

    monkeypatch.setattr(MODULE, "validate_arguments", lambda _args: None)
    monkeypatch.setattr(
        MODULE.target_state, "recover_interrupted_forward",
        lambda *_args: (_ for _ in ()).throw(RuntimeError("marker refused")),
        raising=False,
    )
    monkeypatch.setattr(
        MODULE, "restart_source_writers",
        lambda *_args: pytest.fail("refused marker must keep .182 frozen"),
    )
    with pytest.raises(RuntimeError, match="marker refused"):
        MODULE.execute_recovery(value, Exclusion())


def test_recovery_rollback_preparing_cleans_then_restarts_unraid_and_completes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    value = recovery_arguments(tmp_path, "recover-rollback")
    events: list[str] = []

    class Exclusion:
        def assert_held(self) -> None:
            events.append("lock-held")

    def restart(
        _args: argparse.Namespace, source: str, writers: tuple[str, ...],
    ) -> None:
        assert source == "unraid"
        assert writers == MODULE.WRITER_SERVICES
        events.append("unraid-writers-healthy")

    monkeypatch.setattr(MODULE, "validate_arguments", lambda _args: None)
    monkeypatch.setattr(
        MODULE.target_state, "read_interrupted_rollback_phase",
        lambda *_args: events.append("remote-rollback-preparing")
        or "rollback-preparing",
        raising=False,
    )
    monkeypatch.setattr(
        MODULE.target_state, "complete_interrupted_rollback",
        lambda *_args: events.append("remote-rollback-recovery-complete"),
        raising=False,
    )
    monkeypatch.setattr(
        MODULE, "assert_local_production_stopped",
        lambda _args: events.append("legacy-project-stopped"),
    )
    monkeypatch.setattr(
        MODULE, "clean_rollback_destination",
        lambda _args: events.append("allowlisted-rollback-cleanup"),
    )
    monkeypatch.setattr(MODULE, "restart_source_writers", restart)
    evidence = MODULE.execute_recovery(value, Exclusion())
    assert events == [
        "lock-held", "remote-rollback-preparing", "legacy-project-stopped",
        "lock-held", "allowlisted-rollback-cleanup", "lock-held",
        "unraid-writers-healthy", "lock-held", "remote-rollback-recovery-complete",
    ]
    encoded = json.dumps(evidence, sort_keys=True)
    assert all(
        item in encoded for item in ("rollback-preparing", "erased", "healthy")
    )


def test_recovery_rollback_committed_preserves_both_sides_without_restart(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    value = recovery_arguments(tmp_path, "recover-rollback")
    events: list[str] = []

    class Exclusion:
        def assert_held(self) -> None:
            events.append("lock-held")

    monkeypatch.setattr(MODULE, "validate_arguments", lambda _args: None)
    monkeypatch.setattr(
        MODULE.target_state, "read_interrupted_rollback_phase",
        lambda *_args: events.append("rollback-committed") or "rollback-committed",
        raising=False,
    )
    monkeypatch.setattr(
        MODULE, "clean_rollback_destination",
        lambda _args: pytest.fail("committed rollback data must be preserved"),
    )
    monkeypatch.setattr(
        MODULE, "restart_source_writers",
        lambda *_args: pytest.fail("rollback-committed must keep Unraid frozen"),
    )
    evidence = MODULE.execute_recovery(value, Exclusion())
    assert events == ["lock-held", "rollback-committed"]
    encoded = json.dumps(evidence, sort_keys=True)
    assert "rollback-committed" in encoded and "preserved" in encoded


def test_recovery_rollback_restart_failure_preserves_preparing_journal(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    value = recovery_arguments(tmp_path, "recover-rollback")
    completed: list[bool] = []

    class Exclusion:
        def assert_held(self) -> None:
            pass

    monkeypatch.setattr(MODULE, "validate_arguments", lambda _args: None)
    monkeypatch.setattr(
        MODULE.target_state, "read_interrupted_rollback_phase",
        lambda *_args: "rollback-preparing", raising=False,
    )
    monkeypatch.setattr(MODULE, "assert_local_production_stopped", lambda _args: None)
    monkeypatch.setattr(MODULE, "clean_rollback_destination", lambda _args: None)
    monkeypatch.setattr(
        MODULE, "restart_source_writers",
        lambda *_args: (_ for _ in ()).throw(RuntimeError("restart failed")),
    )
    monkeypatch.setattr(
        MODULE.target_state, "complete_interrupted_rollback",
        lambda *_args: completed.append(True), raising=False,
    )
    with pytest.raises(RuntimeError, match="restart failed"):
        MODULE.execute_recovery(value, Exclusion())
    assert completed == []


@pytest.mark.parametrize(
    "outcome",
    [
        "absent", "preparing", "foreign", "rollback-preparing:short",
        "rollback-committed:" + "1" * 32 + ":" + "z" * 32,
    ],
)
def test_interrupted_rollback_reader_refuses_missing_malformed_or_foreign_state(
    outcome: str,
) -> None:
    with pytest.raises(RuntimeError, match="invalid|refus|marker|state"):
        MODULE.target_state.read_interrupted_rollback_phase(
            lambda *_args, **_kwargs: outcome,
            ["ssh"], lambda script: script,
        )


def test_interrupted_rollback_reader_returns_no_guard_tokens() -> None:
    commands: list[list[str]] = []

    def run(command: list[str], **_kwargs: object) -> str:
        commands.append(command)
        return "rollback-committed"

    assert MODULE.target_state.read_interrupted_rollback_phase(
        run, ["ssh"], lambda script: script,
    ) == "rollback-committed"
    script = commands[0][-1]
    assert "rollback-preparing:" in script and "rollback-committed:" in script
    assert "[0-9a-f]{32}:[0-9a-f]{32}" in script
    assert "regular file:0:0:600:1" in script


def test_rollback_journal_uses_guarded_atomic_preparing_and_commit_transitions() -> None:
    commands: list[list[str]] = []
    guard = MODULE.target_state.TargetGuard("2" * 32)

    def run(command: list[str], **_kwargs: object) -> str:
        commands.append(command)
        return ""

    MODULE.target_state.begin_rollback(
        run, ["ssh"], lambda script: script, guard,
    )
    MODULE.target_state.mark_rollback_committed(
        run, ["ssh"], lambda script: script, guard,
    )
    preparing, committed = (command[-1] for command in commands)
    assert "committed:" in preparing and "rollback-preparing:" in preparing
    assert guard.token in preparing
    assert "rollback-preparing:" in committed and "rollback-committed:" in committed
    assert guard.token in committed
    for script in (preparing, committed):
        assert "mv -T" in script
        assert "sync -f" in script
        assert "chown 0:0" in script and "chmod 0600" in script


def test_recovery_completion_only_consumes_the_matching_restart_journal() -> None:
    commands: list[list[str]] = []

    def run(command: list[str], **_kwargs: object) -> str:
        commands.append(command)
        return ""

    MODULE.target_state.complete_interrupted_forward(
        run, ["ssh"], lambda script: script,
    )
    MODULE.target_state.complete_interrupted_rollback(
        run, ["ssh"], lambda script: script,
    )
    forward, rollback = (command[-1] for command in commands)
    assert "forward-cleaned:" in forward and "[0-9a-f]{32}" in forward
    assert "rm -f" in forward
    assert "rollback-preparing:" in rollback
    assert "[0-9a-f]{32}:[0-9a-f]{32}" in rollback
    assert "committed:" in rollback and "rollback-committed:" not in rollback
    assert "mv -T" in rollback and "sync -f" in rollback


def test_normal_rollback_journal_brackets_every_local_destination_mutation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    value = arguments(tmp_path, "rollback")
    run = MODULE.MigrationRun("unraid", "local-rollback")
    events: list[str] = []
    guard = MODULE.target_state.TargetGuard("1" * 32)

    class Exclusion:
        def assert_held(self) -> None:
            events.append("lock-held")

    monkeypatch.setattr(MODULE, "running_writers", lambda *_args: MODULE.WRITER_SERVICES)
    bypass_source_proofs(monkeypatch)
    monkeypatch.setattr(MODULE, "assert_local_production_stopped", lambda _args: None)
    monkeypatch.setattr(MODULE, "assert_fresh_rollback_project", lambda _args: None)
    monkeypatch.setattr(MODULE.target_state, "new_guard", lambda: guard)
    monkeypatch.setattr(
        MODULE.target_state, "begin_rollback",
        lambda *_args: events.append("rollback-preparing"), raising=False,
    )
    monkeypatch.setattr(
        MODULE, "prepare_rollback",
        lambda _args: events.append("local-destination-mutated")
        or (value.rollback_data_root / ".attachments-migration-test",
            value.rollback_data_root / ".releases-migration-test"),
    )
    monkeypatch.setattr(
        MODULE, "promote_local", lambda *_args: events.append("local-promoted"),
    )
    monkeypatch.setattr(
        MODULE.target_state, "mark_rollback_committed",
        lambda *_args: events.append("rollback-committed"), raising=False,
    )
    MODULE._prepare_run(value, run)
    MODULE._commit_run(value, run, Exclusion())
    assert events.index("rollback-preparing") < events.index("local-destination-mutated")
    assert events.index("local-promoted") < events.index("rollback-committed")
    assert events[events.index("rollback-committed") - 1] == "lock-held"
