"""Cross-host coordination, lock, and CLI dispatch migration tests."""

from __future__ import annotations

import argparse
import builtins
from pathlib import Path

import pytest

from infra.scripts.tests.direct_migration_test_support import (
    MODULE,
    arguments,
    recovery_arguments,
)


def test_coordination_checks_runtime_cron_and_heartbeats() -> None:
    schedule_commands: list[list[str]] = []
    MODULE.coordination.assert_remote_schedules_disabled(
        lambda command: schedule_commands.append(command) or "", ["ssh"],
        MODULE.remote_shell,
    )
    script = schedule_commands[0][-1]
    assert "/tmp/user.scripts/schedule.json" in script
    assert "/var/spool/cron/crontabs/root" in script
    assert '!= \"disabled\"' in script
    token = "a" * 64
    holder = MODULE.coordination.remote_lock_script(token)
    assert MODULE.coordination.REMOTE_LOCK_HELPER in holder
    assert f"hold-migration {token}" in holder
    assert MODULE.coordination.WINDOWS_MUTEX_NAME.startswith("Global\\")


def test_remote_stack_hands_off_only_the_current_lock_capability(tmp_path: Path) -> None:
    value = arguments(tmp_path)
    value.migration_lock_token = "b" * 64
    command = MODULE.remote_stack(value, "ps")
    assert command.startswith(f"LITTLE_ORBIT_MIGRATION_LOCK_TOKEN={'b' * 64} ")
    value.migration_lock_token = "not-a-token"
    with pytest.raises(ValueError, match="lock token"):
        MODULE.remote_stack(value, "ps")


def test_every_direct_remote_command_retains_the_migration_shared_lock(
    tmp_path: Path,
) -> None:
    value = arguments(tmp_path)
    value.migration_lock_token = "e" * 64
    command = MODULE.migration_remote_shell(value, "docker ps")
    assert MODULE.coordination.REMOTE_LOCK_HELPER in command
    assert "run-migration" in command
    assert "docker ps" in command


def test_dead_holder_recovery_reacquires_exclusive_lock_once(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    value = arguments(tmp_path)
    value.migration_lock_token = "f" * 64
    commands: list[str] = []

    class DeadExclusion:
        def assert_held(self) -> None:
            raise RuntimeError("holder ended")

    monkeypatch.setattr(
        MODULE.target_state, "recover_failed_target",
        lambda _run, _ssh, shell, _guard: (
            commands.append(shell("true")) or ("absent", "not-needed", True)
        ),
    )
    observed = MODULE._recover_failure(
        value, "local-production", (), MODULE.target_state.TargetGuard("fixture"),
        False, True, DeadExclusion(),
    )
    assert observed["target_phase"] == "absent"
    assert len(commands) == 1
    assert "run-exclusive" in commands[0]
    assert value.migration_lock_token is None


def test_failed_lock_heartbeat_relinquishes_the_holder(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    lock = MODULE.coordination.RemoteOperationsLock(["unused"])
    stopped: list[bool] = []

    class Input:
        def write(self, _value: str) -> None: pass
        def flush(self) -> None: pass

    class Process:
        stdin = Input()

        def poll(self) -> None:
            return None

    lock._process = Process()
    monkeypatch.setattr(
        MODULE.coordination, "_read_line",
        lambda *_args: (_ for _ in ()).throw(RuntimeError("timeout")),
    )
    monkeypatch.setattr(lock, "_stop", lambda: stopped.append(True) or 0)
    with pytest.raises(RuntimeError, match="no longer held"):
        lock.assert_held()
    assert stopped == [True]


def test_main_keeps_locks_through_commit_and_tolerates_broken_pipe(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    value = arguments(tmp_path)
    events: list[str] = []

    class Parsed:
        def parse_args(self, _argv: object) -> argparse.Namespace:
            return value

    class Exclusion:
        token = "c" * 64

        def __enter__(self) -> Exclusion:
            events.append("locked")
            return self

        def __exit__(self, *_args: object) -> None:
            events.append("unlocked")
            raise OSError("injected post-commit cleanup failure")

    def execute(_args: argparse.Namespace, _guard: object) -> dict[str, object]:
        events.append("committed")
        return {"outcome": "committed"}

    monkeypatch.setattr(MODULE, "parser", Parsed)
    monkeypatch.setattr(MODULE, "validate_arguments", lambda _args: None)
    monkeypatch.setattr(MODULE.safety, "require_routed_local_host", lambda *_args: None)
    monkeypatch.setattr(MODULE.coordination, "MigrationExclusion", lambda **_kwargs: Exclusion())
    monkeypatch.setattr(MODULE, "execute_migration", execute)
    monkeypatch.setattr(builtins, "print", lambda *_args, **_kwargs: (_ for _ in ()).throw(BrokenPipeError()))
    assert MODULE.main([]) == 0
    assert events == ["locked", "committed", "unlocked"]


def test_main_dispatches_recovery_while_both_operation_locks_are_held(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    value = recovery_arguments(tmp_path, "recover-forward")
    events: list[str] = []

    class Parsed:
        def parse_args(self, _argv: object) -> argparse.Namespace:
            return value

    class Exclusion:
        token = "c" * 64

        def __enter__(self) -> Exclusion:
            events.append("both-locks-entered")
            return self

        def __exit__(self, *_args: object) -> None:
            events.append("both-locks-released")

        def assert_held(self) -> None:
            events.append("remote-lock-held")

    def execute(_args: argparse.Namespace, exclusion: Exclusion) -> dict[str, object]:
        assert _args.migration_lock_token == exclusion.token
        events.append("recovery-started")
        exclusion.assert_held()
        return {"outcome": "recovered"}

    monkeypatch.setattr(MODULE, "parser", Parsed)
    monkeypatch.setattr(MODULE, "validate_arguments", lambda _args: None)
    monkeypatch.setattr(MODULE.safety, "require_routed_local_host", lambda *_args: None)
    monkeypatch.setattr(
        MODULE.coordination, "MigrationExclusion", lambda **_kwargs: Exclusion(),
    )
    monkeypatch.setattr(MODULE, "execute_recovery", execute, raising=False)
    monkeypatch.setattr(
        MODULE, "execute_migration",
        lambda *_args: pytest.fail("recovery-only CLI must not start migration"),
    )
    assert MODULE.main([]) == 0
    assert events == [
        "both-locks-entered", "recovery-started", "remote-lock-held",
        "both-locks-released",
    ]
