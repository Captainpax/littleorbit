"""Directly stream Little Orbit state between the fixed .182 and .14 hosts."""

from __future__ import annotations

import argparse
from collections.abc import Mapping, Sequence
import json
from pathlib import Path
import subprocess
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
import migration_inventory as inventory
import migration_local as local_state
import migration_remote as remote
import migration_recovery as recovery
import migration_restart as restart
import migration_safety as safety
import migration_transport as transport
import migration_coordination as coordination
import migration_artifacts as artifacts
import migration_database as database
import migration_evidence as evidence
import migration_target as target_state

run_checked = transport.run_checked
pipe_commands = transport.pipe_commands

LEGACY_HOST = "192.168.50.182"
UNRAID_HOST = "192.168.50.14"
UNRAID_SSH_PORT = 23
UNRAID_STACK = "/mnt/cache/little-orbit-deploy/repo/infra/scripts/unraid-stack.sh"
UNRAID_SECRET_ROOT = "/mnt/cache/little-orbit-secrets"
UNRAID_ENV = f"{UNRAID_SECRET_ROOT}/runtime.env"
UNRAID_BACKUP_IDENTITY = f"{UNRAID_SECRET_ROOT}/backup-age-identity.txt"
LOCAL_DOCKER_HOST = local_state.LOCAL_DOCKER_HOST
ROLLBACK_PROJECT = local_state.ROLLBACK_PROJECT
ATTACHMENT_CONTAINER_ROOT = "/var/lib/little-orbit/attachments"
WRITER_SERVICES = ("gateway", "api", "worker", "media-worker", "context-fetcher")
FORWARD_BUILD_SERVICES = (
    "api", "web", "worker", "media-worker", "context-fetcher", "attachment-init",
    "backup-attachment-reader", "backup-attachment-verifier", "migrate",
)
CONFIRMATIONS = {
    "forward": "forward-.182-to-.14-users-offline",
    "rollback": "post-write-rollback-.14-to-.182-users-offline",
    "recover-forward": "recover-interrupted-forward-.14-state",
    "recover-rollback": "recover-interrupted-rollback-.182-state",
}


class MigrationFailure(RuntimeError):
    """A migration failure with content-free recovery evidence."""

    def __init__(self, recovery: Mapping[str, str]) -> None:
        super().__init__("direct migration failed; inspect structured recovery status")
        self.recovery = dict(recovery)


class MigrationRun:
    def __init__(self, source: str, destination: str) -> None:
        self.source = source
        self.destination = destination
        self.writers: tuple[str, ...] = ()
        self.guard: target_state.TargetGuard | None = None
        self.source_mount: artifacts.AttachmentMount | None = None
        self.attachments: str | Path | None = None
        self.releases: str | Path | None = None
        self.freeze_attempted = False
        self.destination_owned = False


def parser() -> argparse.ArgumentParser:
    """Build a direction-explicit, archive-free migration interface."""

    value = argparse.ArgumentParser(description=__doc__)
    value.add_argument("--direction", required=True, choices=tuple(CONFIRMATIONS))
    value.add_argument("--local-host", default=LEGACY_HOST)
    value.add_argument("--unraid-host", required=True)
    value.add_argument("--unraid-user", default="root")
    value.add_argument("--unraid-port", type=int, default=UNRAID_SSH_PORT)
    value.add_argument("--ssh-identity", type=Path, required=True)
    value.add_argument("--known-hosts", type=Path, required=True)
    value.add_argument("--backup-identity", type=Path)
    value.add_argument(
        "--unraid-stack",
        default=UNRAID_STACK,
    )
    value.add_argument("--local-env", type=Path, default=Path(".env"))
    value.add_argument("--local-release-root", type=Path, default=Path("data/releases"))
    value.add_argument("--rollback-data-root", type=Path)
    value.add_argument("--confirm", required=True)
    return value


local_production_stack = local_state.local_production_stack
local_docker_environment = local_state.local_docker_environment
rollback_environment = local_state.rollback_environment
local_rollback_stack = local_state.local_rollback_stack
ssh_prefix = remote.ssh_prefix
remote_stack = remote.remote_stack
remote_shell = remote.remote_shell
migration_remote_shell = remote.migration_remote_shell
exclusive_remote_shell = remote.exclusive_remote_shell


def stack_command(args: argparse.Namespace, location: str, *values: str) -> list[str]:
    if location == "local-production":
        return local_production_stack(args, *values)
    if location == "local-rollback":
        return local_rollback_stack(args, *values)
    if location == "unraid":
        return [*ssh_prefix(args), remote_stack(args, *values)]
    raise ValueError("unknown migration stack location")


def stack_environment(args: argparse.Namespace, location: str) -> Mapping[str, str] | None:
    if location == "local-rollback":
        return rollback_environment(args)
    if location == "local-production":
        return local_docker_environment(args)
    return None


def validate_arguments(args: argparse.Namespace) -> None:
    if args.unraid_user != "root" or args.unraid_stack != UNRAID_STACK:
        raise ValueError("Unraid root user and fixed stack launcher are required")
    safety.validate_arguments(
        args, confirmations=CONFIRMATIONS, legacy_host=LEGACY_HOST,
        unraid_host=UNRAID_HOST, unraid_port=UNRAID_SSH_PORT,
    )


def run_stack(
    args: argparse.Namespace, location: str, *values: str, capture: bool = False,
) -> str:
    return run_checked(
        stack_command(args, location, *values), capture=capture,
        env=stack_environment(args, location),
    )


def _database_runtime() -> database.Runtime:
    return database.Runtime(run_stack, stack_command, stack_environment, pipe_commands)


def prepare_database(args: argparse.Namespace, location: str) -> None:
    """Start only PostgreSQL and bootstrap its fixed application roles."""

    database.prepare_database(_database_runtime(), args, location)


def assert_no_unexpected_database_sessions(args: argparse.Namespace, location: str) -> None:
    """Require the frozen source database to have no other client session."""

    database.assert_no_unexpected_database_sessions(
        _database_runtime(), args, location,
    )


def database_inventory(args: argparse.Namespace, location: str) -> dict[str, object]:
    """Read exact public table counts and Alembic heads."""

    return database.database_inventory(_database_runtime(), args, location)


def stream_database(args: argparse.Namespace, source: str, destination: str) -> None:
    """Stream a complete custom dump into one fresh database transaction."""

    database.stream_database(_database_runtime(), args, source, destination)


def running_writers(args: argparse.Namespace, location: str) -> tuple[str, ...]:
    """Return all expected running writers, refusing a degraded source."""

    output = run_stack(
        args, location, "ps", "--services", "--status", "running", *WRITER_SERVICES,
        capture=True,
    )
    observed = set(output.splitlines())
    if observed != set(WRITER_SERVICES):
        raise RuntimeError(f"every {location} writer must be running before freeze")
    return tuple(service for service in WRITER_SERVICES if service in observed)


def prove_local_environment_provenance(
    args: argparse.Namespace, source: str,
) -> safety.ProvenLocalSecrets:
    return local_state.prove_local_environment_provenance(
        args, source, run_checked, _artifact_runtime(args),
    )


def assert_local_release_mount(args: argparse.Namespace) -> None:
    local_state.assert_local_release_mount(args, run_checked, run_stack)


def assert_local_production_stopped(args: argparse.Namespace) -> None:
    local_state.assert_local_production_stopped(args, run_checked)


def assert_fresh_rollback_project(args: argparse.Namespace) -> None:
    local_state.assert_fresh_rollback_project(args, run_checked)


def stream_secret(args: argparse.Namespace, source: bytes, target: str, suffix: bytes = b"") -> None:
    artifacts.stream_secret(_artifact_runtime(args), args, source, target, suffix)


def transfer_forward_secrets(
    args: argparse.Namespace, proven: safety.ProvenLocalSecrets,
) -> None:
    if proven.backup_identity is None:
        raise RuntimeError("proven backup identity is unavailable")
    stream_secret(
        args, proven.environment, UNRAID_ENV, artifacts.UNRAID_RUNTIME_OVERRIDES,
    )
    stream_secret(args, proven.backup_identity, UNRAID_BACKUP_IDENTITY)


def _artifact_runtime(args: argparse.Namespace) -> artifacts.Runtime:
    return artifacts.Runtime(
        run=run_checked, run_stack=run_stack, stack_command=stack_command,
        stack_environment=stack_environment, ssh_prefix=ssh_prefix,
        remote_shell=lambda script: migration_remote_shell(args, script),
        pipe=pipe_commands,
        send_file=transport.send_file, send_tar=transport.send_tar,
        receive_release_tar=transport.receive_release_tar,
        remove_tree=transport.remove_tree,
    )


def create_remote_staging(args: argparse.Namespace, kind: str, owner: str) -> str:
    return artifacts.create_remote_staging(_artifact_runtime(args), args, kind, owner)


def create_local_staging(args: argparse.Namespace, kind: str) -> Path:
    return artifacts.create_local_staging(args, kind)


def attachment_inventory(
    args: argparse.Namespace, location: str, stage: str | Path | None = None,
    source_mount: artifacts.AttachmentMount | None = None,
) -> inventory.AttachmentInventory:
    return artifacts.attachment_inventory(
        _artifact_runtime(args), args, location, stage, source_mount,
    )


def prove_source_attachment_mount(
    args: argparse.Namespace, location: str,
) -> artifacts.AttachmentMount:
    return artifacts.prove_source_attachment_mount(_artifact_runtime(args), args, location)


def stream_attachments(
    args: argparse.Namespace, source: str, destination: str, stage: str | Path,
    source_mount: artifacts.AttachmentMount,
) -> None:
    artifacts.stream_attachments(
        _artifact_runtime(args), args, source, destination, stage, source_mount,
    )


def stream_forward_releases(args: argparse.Namespace, stage: str) -> None:
    artifacts.stream_forward_releases(_artifact_runtime(args), args, stage)


def stream_rollback_releases(args: argparse.Namespace, stage: Path) -> None:
    artifacts.stream_rollback_releases(_artifact_runtime(args), args, stage)


def release_inventory_at(
    args: argparse.Namespace, location: str, stage: str | Path | None = None,
) -> dict[str, dict[str, object]]:
    return artifacts.release_inventory_at(_artifact_runtime(args), args, location, stage)


def seal_staging(
    args: argparse.Namespace, location: str, attachments: str | Path,
    releases: str | Path,
) -> None:
    artifacts.seal_staging(_artifact_runtime(args), args, location, attachments, releases)


def promote_remote(
    args: argparse.Namespace, attachments: str, releases: str,
    guard: target_state.TargetGuard,
) -> None:
    artifacts.promote_remote(_artifact_runtime(args), args, attachments, releases, guard)


def promote_local(args: argparse.Namespace, attachments: Path, releases: Path) -> None:
    artifacts.promote_local(args, attachments, releases)


def source_inventory(
    args: argparse.Namespace, location: str,
    source_mount: artifacts.AttachmentMount,
) -> inventory.MigrationInventory:
    """Capture frozen source evidence before streaming begins."""

    return inventory.MigrationInventory(
        database_inventory(args, location),
        attachment_inventory(args, location, source_mount=source_mount),
        release_inventory_at(args, location),
    )


def staged_inventory(
    args: argparse.Namespace, location: str, attachments: str | Path, releases: str | Path,
) -> inventory.MigrationInventory:
    """Capture destination evidence while bytes are still isolated."""

    return inventory.MigrationInventory(
        database_inventory(args, location),
        attachment_inventory(args, location, attachments),
        release_inventory_at(args, location, releases),
    )


def clean_rollback_destination(args: argparse.Namespace) -> None:
    artifacts.clean_rollback_destination(_artifact_runtime(args), args)


def prepare_forward(
    args: argparse.Namespace, proven: safety.ProvenLocalSecrets,
) -> tuple[str, str]:
    """Initialize the already-proven fresh Unraid destination."""

    transfer_forward_secrets(args, proven)
    run_stack(args, "unraid", "build", *FORWARD_BUILD_SERVICES)
    prepare_database(args, "unraid")
    target_state.assert_only_postgres_running(
        run_checked, ssh_prefix(args), lambda script: migration_remote_shell(args, script),
        run_stack, args,
    )
    attachments = create_remote_staging(args, "attachments", "65532:65532")
    releases = create_remote_staging(args, "releases", "root:root")
    return attachments, releases


def prepare_rollback(args: argparse.Namespace) -> tuple[Path, Path]:
    target_state.assert_source_release_mount(
        run_checked, ssh_prefix(args), lambda script: migration_remote_shell(args, script),
        run_stack, args,
    )
    run_stack(args, "local-rollback", "build", "attachment-init")
    prepare_database(args, "local-rollback")
    attachments = create_local_staging(args, "attachments")
    releases = create_local_staging(args, "releases")
    return attachments, releases


def _stream_releases(args: argparse.Namespace, releases: str | Path) -> None:
    if args.direction == "forward":
        stream_forward_releases(args, str(releases))
    else:
        stream_rollback_releases(args, Path(releases))


def _promote(
    args: argparse.Namespace, attachments: str | Path, releases: str | Path,
    guard: target_state.TargetGuard | None,
) -> None:
    if args.direction == "forward":
        if guard is None:
            raise RuntimeError("forward promotion requires a target guard")
        promote_remote(args, str(attachments), str(releases), guard)
    else:
        promote_local(args, Path(attachments), Path(releases))


def restart_source_writers(
    args: argparse.Namespace, source: str, writers: tuple[str, ...],
) -> None:
    """Restart exactly the preflight writers and prove each is ready."""

    restart.restart_source_writers(args, source, writers, run_stack)


def _recover_failure(
    args: argparse.Namespace, source: str, writers: tuple[str, ...],
    guard: target_state.TargetGuard | None, freeze_attempted: bool,
    destination_owned: bool,
    exclusion: coordination.MigrationExclusion | None = None,
) -> dict[str, str]:
    runtime = recovery.Runtime(
        run=run_checked, ssh_prefix=ssh_prefix,
        migration_shell=migration_remote_shell,
        exclusive_shell=exclusive_remote_shell,
        restart_source=restart_source_writers,
        clean_rollback=clean_rollback_destination,
    )
    return recovery.recover_failure(
        runtime, args, source, writers, guard, freeze_attempted,
        destination_owned, exclusion,
    )


def _prepare_run(args: argparse.Namespace, run: MigrationRun) -> None:
    run.writers = running_writers(args, run.source)
    run.source_mount = prove_source_attachment_mount(args, run.source)
    proven = prove_local_environment_provenance(args, run.source)
    if args.direction == "forward":
        assert_local_release_mount(args)
        run.guard = target_state.new_guard()
        target_state.begin_fresh_target(
            run_checked, ssh_prefix(args),
            lambda script: migration_remote_shell(args, script), run.guard,
        )
        run.attachments, run.releases = prepare_forward(args, proven)
        return
    assert_local_production_stopped(args)
    assert_fresh_rollback_project(args)
    run.guard = target_state.new_guard()
    target_state.begin_rollback(
        run_checked, ssh_prefix(args),
        lambda script: migration_remote_shell(args, script), run.guard,
    )
    run.destination_owned = True
    run.attachments, run.releases = prepare_rollback(args)


def _freeze_and_stream(
    args: argparse.Namespace, run: MigrationRun,
) -> tuple[inventory.MigrationInventory, inventory.MigrationInventory]:
    if run.source_mount is None or run.attachments is None or run.releases is None:
        raise RuntimeError("migration staging is incomplete")
    run.freeze_attempted = True
    run_stack(args, run.source, "stop", *WRITER_SERVICES)
    assert_no_unexpected_database_sessions(args, run.source)
    active_ai = inventory.parse_active_ai(run_stack(
        args, run.source, "exec", "-T", "postgres", "sh", "-ec",
        database.psql(inventory.ACTIVE_AI_SQL), capture=True,
    ))
    if any(active_ai.values()):
        raise RuntimeError(
            f"source has active AI work: {json.dumps(active_ai, sort_keys=True)}"
        )
    before = source_inventory(args, run.source, run.source_mount)
    stream_database(args, run.source, run.destination)
    stream_attachments(
        args, run.source, run.destination, run.attachments, run.source_mount,
    )
    _stream_releases(args, run.releases)
    seal_staging(args, run.destination, run.attachments, run.releases)
    after = staged_inventory(args, run.destination, run.attachments, run.releases)
    inventory.assert_destination_matching(before, after, args.direction)
    assert_no_unexpected_database_sessions(args, run.source)
    inventory.assert_matching(
        before, source_inventory(args, run.source, run.source_mount),
    )
    return before, after


def _commit_run(
    args: argparse.Namespace, run: MigrationRun,
    exclusion: coordination.MigrationExclusion | None,
) -> None:
    if run.attachments is None or run.releases is None:
        raise RuntimeError("migration staging is incomplete")
    if exclusion is not None:
        exclusion.assert_held()
    _promote(args, run.attachments, run.releases, run.guard)
    if args.direction == "rollback":
        if run.guard is None:
            raise RuntimeError("rollback promotion requires a target guard")
        if exclusion is not None:
            exclusion.assert_held()
        target_state.mark_rollback_committed(
            run_checked, ssh_prefix(args),
            lambda script: migration_remote_shell(args, script), run.guard,
        )


def execute_migration(
    args: argparse.Namespace,
    exclusion: coordination.MigrationExclusion | None = None,
) -> dict[str, object]:
    validate_arguments(args)
    source, destination = evidence.migration_locations(args.direction)
    run = MigrationRun(source, destination)
    try:
        _prepare_run(args, run)
        before, after = _freeze_and_stream(args, run)
        _commit_run(args, run, exclusion)
    except BaseException as error:
        recovered = _recover_failure(
            args, run.source, run.writers, run.guard, run.freeze_attempted,
            run.destination_owned, exclusion,
        )
        raise MigrationFailure(recovered) from error
    return evidence.success_evidence(
        direction=args.direction,
        source=run.source,
        destination=run.destination,
        before=before,
        after=after,
        legacy_host=LEGACY_HOST,
        unraid_host=UNRAID_HOST,
        rollback_project=ROLLBACK_PROJECT,
    )


def _recover_interrupted_forward(
    args: argparse.Namespace, exclusion: coordination.MigrationExclusion,
) -> dict[str, object]:
    exclusion.assert_held()
    phase, cleanup = target_state.recover_interrupted_forward(
        run_checked, ssh_prefix(args),
        lambda script: migration_remote_shell(args, script),
    )
    source_status = "frozen" if phase == "committed" else "unchanged"
    if phase == "forward-cleaned":
        exclusion.assert_held()
        restart_source_writers(args, "local-production", WRITER_SERVICES)
        exclusion.assert_held()
        target_state.complete_interrupted_forward(
            run_checked, ssh_prefix(args),
            lambda script: migration_remote_shell(args, script),
        )
        source_status = "healthy"
    return {
        "outcome": "recovery-complete", "direction": args.direction,
        "target_phase": phase, "target_cleanup": cleanup,
        "source_writers": source_status,
    }


def _recover_interrupted_rollback(
    args: argparse.Namespace, exclusion: coordination.MigrationExclusion,
) -> dict[str, object]:
    exclusion.assert_held()
    phase = target_state.read_interrupted_rollback_phase(
        run_checked, ssh_prefix(args),
        lambda script: migration_remote_shell(args, script),
    )
    if phase == "rollback-committed":
        return {
            "outcome": "recovery-complete", "direction": args.direction,
            "target_phase": phase, "target_cleanup": "preserved",
            "source_writers": "frozen",
        }
    assert_local_production_stopped(args)
    exclusion.assert_held()
    clean_rollback_destination(args)
    exclusion.assert_held()
    restart_source_writers(args, "unraid", WRITER_SERVICES)
    if phase == "rollback-preparing":
        exclusion.assert_held()
        target_state.complete_interrupted_rollback(
            run_checked, ssh_prefix(args),
            lambda script: migration_remote_shell(args, script),
        )
    return {
        "outcome": "recovery-complete", "direction": args.direction,
        "target_phase": phase, "target_cleanup": "erased",
        "source_writers": "healthy",
    }


def execute_recovery(
    args: argparse.Namespace, exclusion: coordination.MigrationExclusion,
) -> dict[str, object]:
    validate_arguments(args)
    if args.direction == "recover-forward":
        return _recover_interrupted_forward(args, exclusion)
    if args.direction == "recover-rollback":
        return _recover_interrupted_rollback(args, exclusion)
    raise ValueError("recovery requires a recovery-only direction")


def _write_failure(value: str) -> None:
    try:
        print(value, file=sys.stderr)
    except OSError:
        pass


def main(argv: Sequence[str] | None = None) -> int:
    """Run the selected migration direction without a retained raw archive."""

    evidence: dict[str, object] | None = None
    try:
        args = parser().parse_args(argv)
        validate_arguments(args)
        safety.require_routed_local_host(
            LEGACY_HOST, args.unraid_host, args.unraid_port,
        )
        with coordination.MigrationExclusion(
            run=run_checked, ssh=ssh_prefix(args), shell=remote_shell,
        ) as exclusion:
            args.migration_lock_token = exclusion.token
            if args.direction.startswith("recover-"):
                evidence = execute_recovery(args, exclusion)
            else:
                evidence = execute_migration(args, exclusion)
    except MigrationFailure as error:
        _write_failure(json.dumps({
            "outcome": "failed", "recovery": error.recovery,
        }, sort_keys=True))
        return 1
    except (OSError, ValueError, RuntimeError, subprocess.CalledProcessError) as error:
        if evidence is None:
            _write_failure(f"migration failed: {error}")
            return 1
        _write_failure("migration committed; coordination cleanup reported an error")
    assert evidence is not None
    try:
        print(json.dumps(evidence, sort_keys=True))
    except OSError:
        _write_failure("migration committed; success output was unavailable")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
