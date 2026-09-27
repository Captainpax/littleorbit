"""Content-free failure recovery for the direct migration orchestrator."""

from __future__ import annotations

import argparse
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import Protocol

import migration_target as target_state


class Exclusion(Protocol):
    def assert_held(self) -> None: ...


@dataclass(frozen=True)
class Runtime:
    run: Callable[..., str]
    ssh_prefix: Callable[[argparse.Namespace], Sequence[str]]
    migration_shell: Callable[[argparse.Namespace, str], str]
    exclusive_shell: Callable[[str], str]
    restart_source: Callable[..., None]
    clean_rollback: Callable[[argparse.Namespace], None]


def _holder_is_alive(exclusion: Exclusion | None) -> bool:
    if exclusion is None:
        return False
    try:
        exclusion.assert_held()
    except Exception:
        return False
    return True


def _recover_forward_once(
    runtime: Runtime, args: argparse.Namespace,
    guard: target_state.TargetGuard | None, shell: Callable[[str], str],
) -> tuple[str, str, bool]:
    if guard is None:
        return "not-started", "not-needed", True
    try:
        return target_state.recover_failed_target(
            runtime.run, runtime.ssh_prefix(args), shell, guard,
        )
    except Exception:
        return "indeterminate", "not-run", False


def _recover_forward(
    runtime: Runtime, args: argparse.Namespace,
    guard: target_state.TargetGuard | None, exclusion: Exclusion | None,
) -> tuple[str, str, bool]:
    holder_alive = _holder_is_alive(exclusion)
    if not holder_alive:
        args.migration_lock_token = None
    shell = (
        (lambda script: runtime.migration_shell(args, script))
        if holder_alive else runtime.exclusive_shell
    )
    result = _recover_forward_once(runtime, args, guard, shell)
    if result[0] != "indeterminate" or not holder_alive:
        return result if holder_alive else (result[0], result[1], False)
    if _holder_is_alive(exclusion):
        return result
    args.migration_lock_token = None
    result = _recover_forward_once(runtime, args, guard, runtime.exclusive_shell)
    return result[0], result[1], False


def _recover_rollback(
    runtime: Runtime, args: argparse.Namespace, guard: target_state.TargetGuard | None,
    destination_owned: bool, exclusion: Exclusion | None,
) -> tuple[str, str, bool]:
    if not destination_owned:
        return "not-started", "not-needed", True
    if guard is None or not _holder_is_alive(exclusion):
        return "indeterminate", "not-run", False
    def shell(script: str) -> str:
        return runtime.migration_shell(args, script)

    try:
        phase, cleanup, safe = target_state.recover_failed_rollback(
            runtime.run, runtime.ssh_prefix(args), shell, guard,
        )
    except Exception:
        return "indeterminate", "not-run", False
    if not safe:
        return phase, cleanup, False
    try:
        runtime.clean_rollback(args)
    except Exception:
        return phase, "failed", False
    return phase, "erased", True


def _complete_journal(
    runtime: Runtime, args: argparse.Namespace, phase: str,
    guard: target_state.TargetGuard | None, exclusion: Exclusion | None,
) -> bool:
    if guard is None or not _holder_is_alive(exclusion):
        return False
    def shell(script: str) -> str:
        return runtime.migration_shell(args, script)

    try:
        if phase == "forward-cleaned":
            target_state.complete_failed_forward(
                runtime.run, runtime.ssh_prefix(args), shell, guard,
            )
        elif phase == "rollback-preparing":
            target_state.complete_failed_rollback(
                runtime.run, runtime.ssh_prefix(args), shell, guard,
            )
    except Exception:
        return False
    return True


def recover_failure(
    runtime: Runtime, args: argparse.Namespace, source: str,
    writers: tuple[str, ...], guard: target_state.TargetGuard | None,
    freeze_attempted: bool, destination_owned: bool,
    exclusion: Exclusion | None,
) -> dict[str, str]:
    """Clean the incomplete destination before allowing source writers back."""

    if args.direction == "forward":
        phase, cleanup, safe = _recover_forward(runtime, args, guard, exclusion)
    else:
        if not _holder_is_alive(exclusion):
            args.migration_lock_token = None
        phase, cleanup, safe = _recover_rollback(
            runtime, args, guard, destination_owned, exclusion,
        )
    source_status = "unchanged"
    if freeze_attempted:
        source_status = "frozen"
        if safe:
            try:
                runtime.restart_source(args, source, writers)
                source_status = "healthy"
                if not _complete_journal(runtime, args, phase, guard, exclusion):
                    if phase in {"forward-cleaned", "rollback-preparing"}:
                        source_status = "healthy-journal-pending"
            except Exception:
                source_status = "restart-failed"
    return target_state.recovery_record(
        phase=phase, target=cleanup, source=source_status,
    )
