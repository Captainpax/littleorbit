"""Directly stream Little Orbit state between the fixed .182 and .14 hosts."""

from __future__ import annotations

import argparse
from collections.abc import Mapping, Sequence
import json
import os
from pathlib import Path, PurePosixPath
import shlex
import subprocess
import sys
from uuid import uuid4

sys.path.insert(0, str(Path(__file__).resolve().parent))
import migration_inventory as inventory
import migration_safety as safety
import migration_transport as transport

run_checked = transport.run_checked
pipe_commands = transport.pipe_commands

LEGACY_HOST = "192.168.50.182"
UNRAID_HOST = "192.168.50.14"
UNRAID_SSH_PORT = 23
UNRAID_SECRET_ROOT = "/mnt/cache/little-orbit-secrets"
UNRAID_ENV = f"{UNRAID_SECRET_ROOT}/runtime.env"
UNRAID_BACKUP_IDENTITY = f"{UNRAID_SECRET_ROOT}/backup-age-identity.txt"
UNRAID_LIVE_ROOT = "/mnt/cache/little-orbit-live"
UNRAID_ATTACHMENT_ROOT = f"{UNRAID_LIVE_ROOT}/attachments"
UNRAID_RELEASE_ROOT = f"{UNRAID_LIVE_ROOT}/releases"
ROLLBACK_PROJECT = "little-orbit-rollback"
ROLLBACK_VOLUME = f"{ROLLBACK_PROJECT}_postgres-data"
ATTACHMENT_CONTAINER_ROOT = "/var/lib/little-orbit/attachments"
RELEASE_CONTAINER_ROOT = "/var/lib/little-orbit/releases"
WRITER_SERVICES = ("gateway", "api", "worker", "media-worker", "context-fetcher")
CONFIRMATIONS = {
    "forward": "forward-.182-to-.14-users-offline",
    "rollback": "post-write-rollback-.14-to-.182-users-offline",
}


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
        default="/mnt/cache/little-orbit-deploy/repo/infra/scripts/unraid-stack.sh",
    )
    value.add_argument("--local-env", type=Path, default=Path(".env"))
    value.add_argument("--local-release-root", type=Path, default=Path("data/releases"))
    value.add_argument("--rollback-data-root", type=Path)
    value.add_argument("--confirm", required=True)
    return value


def local_production_stack(args: argparse.Namespace, *values: str) -> list[str]:
    return [
        "docker", "compose", "--project-name", "little-orbit",
        "--env-file", str(args.local_env), "-f", "infra/compose.yaml", *values,
    ]


def rollback_environment(args: argparse.Namespace) -> dict[str, str]:
    values = os.environ.copy()
    values["ROLLBACK_DATA_ROOT"] = str(args.rollback_data_root.resolve())
    values["LITTLE_ORBIT_ENV_FILE"] = str(args.local_env.resolve())
    values["ROLLBACK_GATEWAY_BIND_ADDRESS"] = "127.0.0.1"
    values["ROLLBACK_GATEWAY_PORT"] = "18181"
    values["GATEWAY_INTERNAL_SUBNET"] = "10.253.182.0/28"
    values["GATEWAY_CADDY_IP"] = "10.253.182.2"
    values["GATEWAY_API_IP"] = "10.253.182.3"
    return values


def local_rollback_stack(args: argparse.Namespace, *values: str) -> list[str]:
    return [
        "docker", "compose", "--project-name", ROLLBACK_PROJECT,
        "--env-file", str(args.local_env), "-f", "infra/compose.yaml",
        "-f", "infra/compose.rollback.yaml", *values,
    ]


def ssh_prefix(args: argparse.Namespace) -> list[str]:
    return [
        "ssh", "-T", "-p", str(args.unraid_port), "-i", str(args.ssh_identity),
        "-o", "BatchMode=yes", "-o", "StrictHostKeyChecking=yes",
        "-o", f"UserKnownHostsFile={args.known_hosts}",
        f"{args.unraid_user}@{args.unraid_host}",
    ]


def remote_stack(args: argparse.Namespace, *values: str) -> str:
    return " ".join(shlex.quote(item) for item in ("bash", args.unraid_stack, *values))


def remote_shell(script: str) -> str:
    return f"sh -ec {shlex.quote(script)}"


def stack_command(args: argparse.Namespace, location: str, *values: str) -> list[str]:
    if location == "local-production":
        return local_production_stack(args, *values)
    if location == "local-rollback":
        return local_rollback_stack(args, *values)
    if location == "unraid":
        return [*ssh_prefix(args), remote_stack(args, *values)]
    raise ValueError("unknown migration stack location")


def stack_environment(args: argparse.Namespace, location: str) -> Mapping[str, str] | None:
    return rollback_environment(args) if location == "local-rollback" else None


def validate_arguments(args: argparse.Namespace) -> None:
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


def assert_empty_database(args: argparse.Namespace, location: str) -> None:
    """Require every public table in the destination database to be empty."""

    sql = (
        "DO $migration$ DECLARE item record; populated boolean; BEGIN "
        "FOR item IN SELECT tablename FROM pg_tables WHERE schemaname = 'public' LOOP "
        "EXECUTE format('SELECT EXISTS (SELECT 1 FROM %I.%I LIMIT 1)', "
        "'public', item.tablename) INTO populated; IF populated THEN "
        "RAISE EXCEPTION 'destination database is not empty'; END IF; END LOOP; "
        "END $migration$; SELECT 'empty';"
    )
    observed = run_stack(args, location, "exec", "-T", "postgres", "sh", "-ec", _psql(sql), capture=True)
    if observed.strip() != "empty":
        raise RuntimeError("destination database did not prove empty")


def _psql(sql: str) -> str:
    return (
        'psql --username="$POSTGRES_USER" --dbname="$POSTGRES_DB" --quiet '
        f"--tuples-only --no-align --set=ON_ERROR_STOP=1 --command={shlex.quote(sql)}"
    )


def prepare_database(args: argparse.Namespace, location: str) -> None:
    """Start only PostgreSQL and bootstrap its fixed application roles."""

    run_stack(args, location, "up", "-d", "--wait", "postgres")
    assert_empty_database(args, location)
    run_stack(args, location, "run", "--rm", "-T", "database-bootstrap")


def database_inventory(args: argparse.Namespace, location: str) -> dict[str, object]:
    """Read exact public table counts and Alembic heads."""

    raw = run_stack(
        args, location, "exec", "-T", "postgres", "sh", "-ec",
        _psql(inventory.DATABASE_INVENTORY_SQL), capture=True,
    )
    return inventory.parse_database_inventory(raw)


def stream_database(args: argparse.Namespace, source: str, destination: str) -> None:
    """Stream a complete custom dump into one fresh database transaction."""

    dump = (
        'pg_dump --format=custom --no-owner --username="$POSTGRES_USER" '
        '"$POSTGRES_DB"'
    )
    restore = (
        "pg_restore --clean --if-exists --no-owner --single-transaction "
        '--exit-on-error --username="$POSTGRES_USER" --dbname="$POSTGRES_DB"'
    )
    producer = stack_command(args, source, "exec", "-T", "postgres", "sh", "-ec", dump)
    consumer = stack_command(args, destination, "exec", "-T", "postgres", "sh", "-ec", restore)
    pipe_commands(
        producer, consumer, source_env=stack_environment(args, source),
        destination_env=stack_environment(args, destination),
    )
    run_stack(args, destination, "run", "--rm", "-T", "database-bootstrap")


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


def assert_local_production_stopped(args: argparse.Namespace) -> None:
    """Never let rollback reuse or mutate the stale production project."""

    del args
    running = run_checked([
        "docker", "ps", "--filter", "label=com.docker.compose.project=little-orbit",
        "--format", "{{.ID}}",
    ], capture=True)
    if running:
        raise RuntimeError("the old little-orbit project must be completely stopped")


def assert_fresh_rollback_project(args: argparse.Namespace) -> None:
    """Reject stale containers or a pre-existing rollback database volume."""

    del args
    containers = run_checked([
        "docker", "ps", "-aq", "--filter",
        f"label=com.docker.compose.project={ROLLBACK_PROJECT}",
    ], capture=True)
    if containers:
        raise RuntimeError("rollback project already has containers")
    result = subprocess.run(
        ["docker", "volume", "inspect", ROLLBACK_VOLUME], text=True,
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    if result.returncode == 0:
        raise RuntimeError("rollback PostgreSQL volume already exists")


def assert_empty_unraid_storage(args: argparse.Namespace) -> None:
    """Require existing, empty live directories before forward staging."""

    guards: list[str] = []
    for path in (UNRAID_ATTACHMENT_ROOT, UNRAID_RELEASE_ROOT):
        quoted = shlex.quote(path)
        guards.extend((f"test -d {quoted}", f"test -z \"$(find {quoted} -mindepth 1 -maxdepth 1 -print -quit)\""))
    run_checked([*ssh_prefix(args), remote_shell("; ".join(guards))])


def stream_secret(args: argparse.Namespace, source: Path, target: str, suffix: bytes = b"") -> None:
    """Install one root-only Unraid secret atomically without logging it."""

    if target not in {UNRAID_ENV, UNRAID_BACKUP_IDENTITY}:
        raise ValueError("secret target is not allowlisted")
    name = Path(target).name
    temporary = f"{UNRAID_SECRET_ROOT}/.{name}.XXXXXX"
    script = (
        f"umask 077; install -d -m 0700 {shlex.quote(UNRAID_SECRET_ROOT)}; "
        f"temporary=$(mktemp {shlex.quote(temporary)}); trap 'rm -f -- \"$temporary\"' EXIT; "
        f"cat > \"$temporary\"; test -s \"$temporary\"; chmod 0600 \"$temporary\"; "
        f"if test -e {shlex.quote(target)}; then cmp -s \"$temporary\" {shlex.quote(target)} || exit 78; "
        f"rm -f -- \"$temporary\"; else mv -- \"$temporary\" {shlex.quote(target)}; fi; trap - EXIT"
    )
    transport.send_file([*ssh_prefix(args), remote_shell(script)], source, suffix)


def transfer_forward_secrets(args: argparse.Namespace) -> None:
    """Transfer existing secrets plus fixed Unraid host-only settings."""

    overrides = (
        b"\nLITTLE_ORBIT_ENV=production\nGATEWAY_BIND_ADDRESS=192.168.50.14\n"
        b"GATEWAY_INTERNAL_SUBNET=10.253.14.0/28\nGATEWAY_CADDY_IP=10.253.14.2\n"
        b"GATEWAY_API_IP=10.253.14.3\nLITTLE_ORBIT_DATA_ROOT=/mnt/cache/little-orbit-live\n"
        b"RELEASE_STORAGE_ROOT=/mnt/cache/little-orbit-live/releases\n"
        b"GPU_COORDINATOR_ROOT=/mnt/cache/gpu-coordinator\n"
        b"GPU_LOCK_HOST_PATH=/mnt/cache/gpu-coordinator/gpu.lock\nGPU_COORDINATOR_GID=2000\n"
        b"LITTLE_ORBIT_BACKUP_ROOT=/mnt/user/little-orbit-backups\n"
        b"LITTLE_ORBIT_ENV_FILE=/mnt/cache/little-orbit-secrets/runtime.env\n"
        b"GPU_LOCK_PATH=/run/gpu-coordinator/gpu.lock\nGPU_VERIFY_IDLE_PROCESSES=true\n"
    )
    stream_secret(args, args.local_env, UNRAID_ENV, overrides)
    stream_secret(args, args.backup_identity, UNRAID_BACKUP_IDENTITY)


def create_remote_staging(args: argparse.Namespace, kind: str, owner: str) -> str:
    """Create a validated sibling staging directory on the Unraid cache pool."""

    prefix = f".{kind}-migration-"
    template = f"{UNRAID_LIVE_ROOT}/{prefix}XXXXXX"
    script = (
        f"umask 077; staging=$(mktemp -d {shlex.quote(template)}); "
        f"chown {shlex.quote(owner)} \"$staging\"; printf '%s\\n' \"$staging\""
    )
    path = run_checked([*ssh_prefix(args), remote_shell(script)], capture=True)
    if PurePosixPath(path).parent != PurePosixPath(UNRAID_LIVE_ROOT) or not PurePosixPath(path).name.startswith(prefix):
        raise RuntimeError("Unraid returned an invalid staging path")
    return path


def create_local_staging(args: argparse.Namespace, kind: str) -> Path:
    """Create a private sibling stage inside the explicit rollback root."""

    path = Path(args.rollback_data_root) / f".{kind}-migration-{uuid4().hex}"
    path.mkdir(mode=0o700)
    return path


def _program(name: str) -> str:
    """Read a reviewed migration helper for an in-container one-shot."""

    return (Path(__file__).resolve().parent / name).read_text(encoding="utf-8")


def attachment_command(
    args: argparse.Namespace, location: str, program: str, *,
    stage: str | Path | None = None, restore: bool = False,
) -> list[str]:
    """Build an attachment stream, restore, or inventory one-shot."""

    values = ["run", "--rm", "-T", "--no-deps"]
    if stage is not None:
        values.extend(("--volume", f"{stage}:{ATTACHMENT_CONTAINER_ROOT}"))
    if restore:
        values.extend(("--user", "0:0" if location == "local-rollback" else "65532:65532"))
        values.extend(("--env", "LITTLE_ORBIT_ATTACHMENT_RESTORE_MODE=stage"))
    values.extend(("--entrypoint", "python", "attachment-init", "-c", program))
    if not restore:
        values.extend(("attachments", ATTACHMENT_CONTAINER_ROOT))
    return stack_command(args, location, *values)


def attachment_inventory(
    args: argparse.Namespace, location: str, stage: str | Path | None = None,
) -> inventory.AttachmentInventory:
    """Read aggregate-only attachment evidence from a live or staged root."""

    command = attachment_command(args, location, _program("migration_inventory.py"), stage=stage)
    raw = run_checked(command, capture=True, env=stack_environment(args, location))
    return inventory.parse_attachment_inventory(raw)


def stream_attachments(
    args: argparse.Namespace, source: str, destination: str, stage: str | Path,
) -> None:
    """Stream verified attachment bytes into a disposable sibling directory."""

    producer = attachment_command(args, source, _program("stream-attachment-backup.py"))
    consumer = attachment_command(
        args, destination, _program("restore-attachment-backup.py"),
        stage=stage, restore=True,
    )
    pipe_commands(
        producer, consumer, source_env=stack_environment(args, source),
        destination_env=stack_environment(args, destination),
    )
    if destination == "local-rollback":
        run_stack(
            args, destination, "run", "--rm", "-T", "--no-deps", "--user", "0:0",
            "--volume", f"{stage}:{ATTACHMENT_CONTAINER_ROOT}", "--entrypoint", "sh",
            "attachment-init", "-ec", f"chown -R 65532:65532 {ATTACHMENT_CONTAINER_ROOT}",
        )


def stream_forward_releases(args: argparse.Namespace, stage: str) -> None:
    """Stream immutable `.182` release bytes into Unraid sibling staging."""

    destination = [*ssh_prefix(args), f"tar -xpf - -C {shlex.quote(stage)}"]
    transport.send_tar(destination, args.local_release_root)


def stream_rollback_releases(args: argparse.Namespace, stage: Path) -> None:
    """Safely extract immutable Unraid release bytes into local sibling staging."""

    source = [*ssh_prefix(args), f"tar -cpf - -C {shlex.quote(UNRAID_RELEASE_ROOT)} ."]
    transport.receive_release_tar(source, stage)


def release_inventory_at(
    args: argparse.Namespace, location: str, stage: str | Path | None = None,
) -> dict[str, dict[str, object]]:
    """Read immutable release size/hash evidence from host or container."""

    if location == "local-production":
        return inventory.release_inventory(args.local_release_root)
    if location == "local-rollback":
        if stage is None:
            raise ValueError("rollback release inventory requires a staging path")
        return inventory.release_inventory(Path(stage))
    values = ["run", "--rm", "-T", "--no-deps"]
    if stage is not None:
        values.extend(("--volume", f"{stage}:{RELEASE_CONTAINER_ROOT}:ro"))
    values.extend((
        "--entrypoint", "python", "api", "-c", _program("migration_inventory.py"),
        "releases", RELEASE_CONTAINER_ROOT,
    ))
    raw = run_stack(args, "unraid", *values, capture=True)
    return inventory.parse_release_inventory(raw)


def seal_staging(args: argparse.Namespace, location: str, attachments: str | Path, releases: str | Path) -> None:
    """Apply final ownership and read-only release modes before promotion."""

    if location == "unraid":
        quoted = shlex.quote(str(releases))
        script = f"find {quoted} -type d -exec chmod 0555 {{}} +; find {quoted} -type f -exec chmod 0444 {{}} +"
        run_checked([*ssh_prefix(args), remote_shell(script)])
        return
    for path in sorted(Path(releases).rglob("*"), reverse=True):
        path.chmod(0o555 if path.is_dir() else 0o444)
    Path(releases).chmod(0o555)


def promote_remote(args: argparse.Namespace, attachments: str, releases: str) -> None:
    """Rename complete sibling trees over empty live directories."""

    attachment_target = shlex.quote(UNRAID_ATTACHMENT_ROOT)
    release_target = shlex.quote(UNRAID_RELEASE_ROOT)
    attachment_stage = shlex.quote(attachments)
    release_stage = shlex.quote(releases)
    guards = (
        f"test -z \"$(find {attachment_target} -mindepth 1 -maxdepth 1 -print -quit)\"; "
        f"test -z \"$(find {release_target} -mindepth 1 -maxdepth 1 -print -quit)\"; "
    )
    promote = (
        f"mv -T -- {attachment_stage} {attachment_target}; "
        f"if mv -T -- {release_stage} {release_target}; then :; "
        f"else mv -T -- {attachment_target} {attachment_stage}; exit 1; fi"
    )
    run_checked([*ssh_prefix(args), remote_shell(guards + promote)])


def promote_local(args: argparse.Namespace, attachments: Path, releases: Path) -> None:
    """Atomically rename complete staged trees into the absent rollback paths."""

    attachment_target = args.rollback_data_root / "attachments"
    release_target = args.rollback_data_root / "releases"
    if attachment_target.exists() or release_target.exists():
        raise RuntimeError("rollback destination paths must remain absent before promotion")
    os.replace(attachments, attachment_target)
    try:
        os.replace(releases, release_target)
    except BaseException:
        os.replace(attachment_target, attachments)
        raise


def source_inventory(args: argparse.Namespace, location: str) -> inventory.MigrationInventory:
    """Capture frozen source evidence before streaming begins."""

    return inventory.MigrationInventory(
        database_inventory(args, location),
        attachment_inventory(args, location),
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


def remove_remote_staging(args: argparse.Namespace, path: str) -> None:
    """Remove only an allowlisted, unpromoted Unraid sibling stage."""

    value = PurePosixPath(path)
    allowed = (".attachments-migration-", ".releases-migration-")
    if value.parent != PurePosixPath(UNRAID_LIVE_ROOT) or not value.name.startswith(allowed):
        return
    run_checked([*ssh_prefix(args), remote_shell(f"rm -rf -- {shlex.quote(path)}")])


def clean_rollback_destination(args: argparse.Namespace) -> None:
    run_stack(args, "local-rollback", "down", "--volumes", "--remove-orphans")
    root = args.rollback_data_root.resolve()
    for child in root.iterdir():
        resolved = child.resolve()
        if resolved.parent != root:
            raise RuntimeError("rollback cleanup escaped the dedicated root")
        allowed = child.name in {"attachments", "releases"} or child.name.startswith(
            (".attachments-migration-", ".releases-migration-")
        )
        if not allowed:
            raise RuntimeError("rollback cleanup found an unexpected path")
        if child.is_dir() and not child.is_symlink():
            transport.remove_tree(child)
        else:
            child.unlink()


def prepare_forward(args: argparse.Namespace) -> tuple[str, str, tuple[str, ...]]:
    """Prepare the empty Unraid destination before the source freeze."""

    writers = running_writers(args, "local-production")
    assert_empty_unraid_storage(args)
    transfer_forward_secrets(args)
    prepare_database(args, "unraid")
    attachments = create_remote_staging(args, "attachments", "65532:65532")
    try:
        releases = create_remote_staging(args, "releases", "root:root")
    except BaseException:
        remove_remote_staging(args, attachments)
        raise
    return attachments, releases, writers


def prepare_rollback(args: argparse.Namespace) -> tuple[Path, Path, tuple[str, ...]]:
    """Prepare a fresh isolated `.182` destination before freezing Unraid."""

    assert_local_production_stopped(args)
    assert_fresh_rollback_project(args)
    try:
        run_stack(args, "local-rollback", "build", "attachment-init")
        prepare_database(args, "local-rollback")
        writers = running_writers(args, "unraid")
        attachments = create_local_staging(args, "attachments")
        releases = create_local_staging(args, "releases")
    except BaseException as error:
        try:
            clean_rollback_destination(args)
        except Exception as cleanup_error:
            error.add_note(f"rollback preparation cleanup also failed: {cleanup_error}")
        raise
    return attachments, releases, writers


def _migration_locations(direction: str) -> tuple[str, str]:
    return (
        ("local-production", "unraid")
        if direction == "forward"
        else ("unraid", "local-rollback")
    )


def _stream_releases(args: argparse.Namespace, releases: str | Path) -> None:
    if args.direction == "forward":
        stream_forward_releases(args, str(releases))
    else:
        stream_rollback_releases(args, Path(releases))


def _promote(args: argparse.Namespace, attachments: str | Path, releases: str | Path) -> None:
    if args.direction == "forward":
        promote_remote(args, str(attachments), str(releases))
    else:
        promote_local(args, Path(attachments), Path(releases))


def _recover_failure(
    args: argparse.Namespace, source: str, writers: tuple[str, ...],
    attachments: str | Path, releases: str | Path, error: BaseException,
) -> None:
    try:
        run_stack(args, source, "start", *writers)
    except Exception as restart_error:
        error.add_note(f"source writer restart also failed: {restart_error}")
    try:
        if args.direction == "forward":
            remove_remote_staging(args, str(attachments))
            remove_remote_staging(args, str(releases))
        else:
            clean_rollback_destination(args)
    except Exception as cleanup_error:
        error.add_note(f"migration cleanup also failed: {cleanup_error}")


def execute_migration(args: argparse.Namespace) -> None:
    """Freeze, stream, verify, promote, and leave the old source frozen."""

    validate_arguments(args)
    source, destination = _migration_locations(args.direction)
    attachments, releases, writers = (
        prepare_forward(args) if args.direction == "forward" else prepare_rollback(args)
    )
    try:
        run_stack(args, source, "stop", *WRITER_SERVICES)
        active_ai = inventory.parse_active_ai(run_stack(
            args, source, "exec", "-T", "postgres", "sh", "-ec",
            _psql(inventory.ACTIVE_AI_SQL), capture=True,
        ))
        if any(active_ai.values()):
            raise RuntimeError(f"source has active AI work: {json.dumps(active_ai, sort_keys=True)}")
        before = source_inventory(args, source)
        stream_database(args, source, destination)
        stream_attachments(args, source, destination, attachments)
        _stream_releases(args, releases)
        seal_staging(args, destination, attachments, releases)
        after = staged_inventory(args, destination, attachments, releases)
        inventory.assert_matching(before, after)
        _promote(args, attachments, releases)
    except BaseException as error:
        _recover_failure(args, source, writers, attachments, releases, error)
        raise
    evidence = {
        "outcome": "streamed-and-matched", "direction": args.direction,
        "source": {"host": LEGACY_HOST if source == "local-production" else UNRAID_HOST,
                   "inventory": before.serializable()},
        "destination": {"host": UNRAID_HOST if destination == "unraid" else LEGACY_HOST,
                        "project": "little-orbit" if destination == "unraid" else ROLLBACK_PROJECT,
                        "inventory": after.serializable()},
        "source_writers": "stopped", "inventories_match": True,
    }
    print(json.dumps(evidence, sort_keys=True))


def main(argv: Sequence[str] | None = None) -> int:
    """Run the selected migration direction without a retained raw archive."""

    try:
        args = parser().parse_args(argv)
        validate_arguments(args)
        safety.require_routed_local_host(
            LEGACY_HOST, args.unraid_host, args.unraid_port,
        )
        execute_migration(args)
    except (OSError, ValueError, RuntimeError, subprocess.CalledProcessError) as error:
        print(f"migration failed: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
