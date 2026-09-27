"""Secret and filesystem artifact operations for direct migration."""

from __future__ import annotations

import argparse
from collections.abc import Callable, Mapping
from dataclasses import dataclass
import json
import os
from pathlib import Path, PurePosixPath
import shlex
from uuid import uuid4

import migration_inventory as inventory
import migration_safety as safety
import migration_target as target_state


UNRAID_SECRET_ROOT = "/mnt/cache/little-orbit-secrets"
UNRAID_ENV = f"{UNRAID_SECRET_ROOT}/runtime.env"
UNRAID_BACKUP_IDENTITY = f"{UNRAID_SECRET_ROOT}/backup-age-identity.txt"
UNRAID_LIVE_ROOT = "/mnt/cache/little-orbit-live"
UNRAID_ATTACHMENT_ROOT = f"{UNRAID_LIVE_ROOT}/attachments"
UNRAID_RELEASE_ROOT = f"{UNRAID_LIVE_ROOT}/releases"
ATTACHMENT_CONTAINER_ROOT = "/var/lib/little-orbit/attachments"
RELEASE_CONTAINER_ROOT = "/var/lib/little-orbit/releases"
UNRAID_RUNTIME_OVERRIDES = (
    b"\nLITTLE_ORBIT_ENV=production\nPUBLIC_BASE_URL=https://lil-orb.pax-kun.com\n"
    b"GATEWAY_BIND_ADDRESS=192.168.50.14\n"
    b"GATEWAY_INTERNAL_SUBNET=10.253.14.0/28\nGATEWAY_CADDY_IP=10.253.14.2\n"
    b"GATEWAY_API_IP=10.253.14.3\nTRUSTED_PROXY_IP=10.253.14.2\n"
    b"LITTLE_ORBIT_DATA_ROOT=/mnt/cache/little-orbit-live\n"
    b"RELEASE_STORAGE_ROOT=/mnt/cache/little-orbit-live/releases\n"
    b"GPU_COORDINATOR_ROOT=/mnt/cache/gpu-coordinator\n"
    b"GPU_LOCK_HOST_PATH=/mnt/cache/gpu-coordinator/gpu.lock\nGPU_COORDINATOR_GID=2000\n"
    b"LITTLE_ORBIT_BACKUP_ROOT=/mnt/user/little-orbit-backups\n"
    b"LITTLE_ORBIT_ENV_FILE=/mnt/cache/little-orbit-secrets/runtime.env\n"
    b"GPU_LOCK_PATH=/run/gpu-coordinator/gpu.lock\nGPU_VERIFY_IDLE_PROCESSES=true\n"
    b"AI_SCHEDULE_TIMEZONE=America/Los_Angeles\nAI_LEARNING_LOCAL_HOUR=1\n"
    b"AI_GENERATION_LOCAL_HOUR=3\nAI_WORK_RETRY_HOURS=6\n"
    b"AI_WORK_MAX_RUNTIME_SECONDS=6600\nAI_COVERAGE_DAYS=14\n"
)


@dataclass(frozen=True)
class Runtime:
    """Call boundaries supplied by the CLI for isolated unit testing."""

    run: Callable[..., str]
    run_stack: Callable[..., str]
    stack_command: Callable[..., list[str]]
    stack_environment: Callable[..., Mapping[str, str] | None]
    ssh_prefix: Callable[..., list[str]]
    remote_shell: Callable[[str], str]
    pipe: Callable[..., None]
    send_file: Callable[..., None]
    send_tar: Callable[..., None]
    receive_release_tar: Callable[..., None]
    remove_tree: Callable[[Path], None]


@dataclass(frozen=True)
class AttachmentMount:
    """Exact Docker mount shared by every running source attachment writer."""

    kind: str
    source: str
    volume_name: str

    @property
    def compose_source(self) -> str:
        return self.volume_name if self.kind == "volume" else self.source


def stream_secret(
    runtime: Runtime, args: argparse.Namespace, source: bytes, target: str,
    suffix: bytes = b"",
) -> None:
    """Install one root-only Unraid secret atomically without logging it."""

    if target not in {UNRAID_ENV, UNRAID_BACKUP_IDENTITY}:
        raise ValueError("secret target is not allowlisted")
    temporary = f"{UNRAID_SECRET_ROOT}/.{Path(target).name}.XXXXXX"
    script = (
        f"umask 077; test ! -L {shlex.quote(UNRAID_SECRET_ROOT)}; "
        f"install -d -o 0 -g 0 -m 0700 {shlex.quote(UNRAID_SECRET_ROOT)}; "
        f"test \"$(stat -c '%u:%g:%a' {shlex.quote(UNRAID_SECRET_ROOT)})\" = 0:0:700; "
        f"temporary=$(mktemp {shlex.quote(temporary)}); trap 'rm -f -- \"$temporary\"' EXIT; "
        f"cat > \"$temporary\"; test -s \"$temporary\"; chmod 0600 \"$temporary\"; "
        f"if test -e {shlex.quote(target)} || test -L {shlex.quote(target)}; then "
        f"test -f {shlex.quote(target)}; test ! -L {shlex.quote(target)}; "
        f"test \"$(stat -c '%F:%u:%g:%a:%h' {shlex.quote(target)})\" = "
        f"'regular file:0:0:600:1'; "
        f"cmp -s \"$temporary\" {shlex.quote(target)} || exit 78; "
        f"rm -f -- \"$temporary\"; else mv -- \"$temporary\" {shlex.quote(target)}; fi; "
        f"test \"$(stat -c '%F:%u:%g:%a:%h' {shlex.quote(target)})\" = "
        f"'regular file:0:0:600:1'; trap - EXIT"
    )
    runtime.send_file(
        [*runtime.ssh_prefix(args), runtime.remote_shell(script)], source, suffix,
        rebuild_env=target == UNRAID_ENV,
    )


def create_remote_staging(
    runtime: Runtime, args: argparse.Namespace, kind: str, owner: str,
) -> str:
    """Create a validated sibling staging directory on the cache pool."""

    prefix = f".{kind}-migration-"
    template = f"{UNRAID_LIVE_ROOT}/{prefix}XXXXXX"
    script = (
        f"umask 077; staging=$(mktemp -d {shlex.quote(template)}); "
        f"chown {shlex.quote(owner)} \"$staging\"; printf '%s\\n' \"$staging\""
    )
    path = runtime.run(
        [*runtime.ssh_prefix(args), runtime.remote_shell(script)], capture=True,
    )
    parsed = PurePosixPath(path)
    if parsed.parent != PurePosixPath(UNRAID_LIVE_ROOT) or not parsed.name.startswith(prefix):
        raise RuntimeError("Unraid returned an invalid staging path")
    return path


def create_local_staging(args: argparse.Namespace, kind: str) -> Path:
    """Create a private sibling stage inside the explicit rollback root."""

    root = safety.prove_rollback_root(args.rollback_root_guard)
    path = root / f".{kind}-migration-{uuid4().hex}"
    path.mkdir(mode=0o700)
    return path


def _program(name: str) -> str:
    return (Path(__file__).resolve().parent / name).read_text(encoding="utf-8")


def _inventory_program() -> str:
    """Return the self-contained inventory used by one-shot containers."""

    return _program("migration_file_inventory.py")


def _container_id(
    runtime: Runtime, args: argparse.Namespace, location: str, service: str,
) -> str:
    value = runtime.run_stack(args, location, "ps", "-q", service, capture=True)
    if not 12 <= len(value) <= 64 or "\n" in value or not all(
        character in "0123456789abcdef" for character in value.lower()
    ):
        raise RuntimeError("source attachment container identity is ambiguous")
    return value


def _mounts_json(
    runtime: Runtime, args: argparse.Namespace, location: str, container: str,
) -> str:
    template = "{{json .Mounts}}"
    if location == "unraid":
        command = [
            *runtime.ssh_prefix(args),
            runtime.remote_shell(
                "docker inspect --format "
                f"{shlex.quote(template)} {shlex.quote(container)}"
            ),
        ]
    else:
        command = ["docker", "inspect", "--format", template, container]
    return runtime.run(
        command, capture=True, env=runtime.stack_environment(args, location),
    )


def container_environment(
    runtime: Runtime, args: argparse.Namespace, location: str, service: str,
) -> dict[str, str]:
    """Read a running source service's environment without logging any value."""

    container = _container_id(runtime, args, location, service)
    template = "{{json .Config.Env}}"
    if location == "unraid":
        command = [
            *runtime.ssh_prefix(args),
            runtime.remote_shell(
                "docker inspect --format "
                f"{shlex.quote(template)} {shlex.quote(container)}"
            ),
        ]
    else:
        command = ["docker", "inspect", "--format", template, container]
    raw = runtime.run(
        command, capture=True, env=runtime.stack_environment(args, location),
    )
    try:
        parsed = json.loads(raw)
    except (json.JSONDecodeError, TypeError) as error:
        raise RuntimeError("source service environment inventory is invalid") from error
    if not isinstance(parsed, list) or not all(isinstance(item, str) for item in parsed):
        raise RuntimeError("source service environment inventory is invalid")
    values: dict[str, str] = {}
    for item in parsed:
        if "=" not in item:
            raise RuntimeError("source service environment inventory is invalid")
        name, value = item.split("=", maxsplit=1)
        if not name or name in values:
            raise RuntimeError("source service environment inventory is ambiguous")
        values[name] = value
    return values


def _attachment_mount_entry(raw: str) -> dict[str, object]:
    try:
        parsed = json.loads(raw)
    except (json.JSONDecodeError, TypeError) as error:
        raise RuntimeError("source attachment mount inventory is invalid") from error
    if not isinstance(parsed, list):
        raise RuntimeError("source attachment mount inventory is invalid")
    entries = []
    for entry in parsed:
        if not isinstance(entry, dict):
            continue
        if entry.get("Destination") == ATTACHMENT_CONTAINER_ROOT:
            entries.append(entry)
    if len(entries) != 1:
        raise RuntimeError("source attachment mount is missing or ambiguous")
    return entries[0]


def _attachment_mount(raw: str) -> AttachmentMount:
    entry = _attachment_mount_entry(raw)
    kind = entry.get("Type")
    source = entry.get("Source")
    name = entry.get("Name", "")
    if not isinstance(kind, str) or kind not in {"bind", "volume"}:
        raise RuntimeError("source attachment mount boundary is invalid")
    if not isinstance(source, str) or not source:
        raise RuntimeError("source attachment mount boundary is invalid")
    if not isinstance(name, str) or entry.get("RW") is not True:
        raise RuntimeError("source attachment mount boundary is invalid")
    if kind == "volume" and not name:
        raise RuntimeError("source attachment volume identity is missing")
    if kind == "bind" and name:
        raise RuntimeError("source attachment bind identity is invalid")
    return AttachmentMount(kind, source, name)


def prove_source_attachment_mount(
    runtime: Runtime, args: argparse.Namespace, location: str,
) -> AttachmentMount:
    """Tie migration reads to the exact mount used by all live source writers."""

    mounts = []
    for service in ("api", "worker", "media-worker"):
        container = _container_id(runtime, args, location, service)
        mounts.append(_attachment_mount(_mounts_json(runtime, args, location, container)))
    if mounts[1:] != mounts[:-1]:
        raise RuntimeError("source attachment writers do not share one exact mount")
    mount = mounts[0]
    if location == "unraid" and (
        mount.kind != "bind" or mount.source != UNRAID_ATTACHMENT_ROOT
    ):
        raise RuntimeError("Unraid source attachment mount is not the fixed live root")
    return mount


def attachment_command(
    runtime: Runtime, args: argparse.Namespace, location: str, program: str, *,
    stage: str | Path | None = None, restore: bool = False,
    source_mount: AttachmentMount | None = None,
) -> list[str]:
    """Build a least-privilege attachment one-shot."""

    values = ["run", "--rm", "-T", "--no-deps"]
    if stage is not None:
        values.extend((
            "--volume",
            f"{stage}:{ATTACHMENT_CONTAINER_ROOT}{'' if restore else ':ro'}",
        ))
    elif not restore:
        if source_mount is None:
            raise ValueError("source attachment inventory requires a proven mount")
        values.extend((
            "--volume",
            f"{source_mount.compose_source}:{ATTACHMENT_CONTAINER_ROOT}:ro",
        ))
    if restore:
        user = "0:0" if location == "local-rollback" else "65532:65532"
        values.extend(("--user", user, "--env", "LITTLE_ORBIT_ATTACHMENT_RESTORE_MODE=stage"))
    service = "attachment-init" if restore else "backup-attachment-reader"
    values.extend(("--entrypoint", "python", service, "-c", program))
    if not restore:
        values.extend(("attachments", ATTACHMENT_CONTAINER_ROOT))
    return runtime.stack_command(args, location, *values)


def attachment_inventory(
    runtime: Runtime, args: argparse.Namespace, location: str,
    stage: str | Path | None = None,
    source_mount: AttachmentMount | None = None,
) -> inventory.AttachmentInventory:
    command = attachment_command(
        runtime, args, location, _inventory_program(), stage=stage,
        source_mount=source_mount,
    )
    raw = runtime.run(
        command, capture=True, env=runtime.stack_environment(args, location),
    )
    return inventory.parse_attachment_inventory(raw)


def stream_attachments(
    runtime: Runtime, args: argparse.Namespace, source: str, destination: str,
    stage: str | Path, source_mount: AttachmentMount,
) -> None:
    """Stream verified attachment bytes into an isolated sibling."""

    producer = attachment_command(
        runtime, args, source, _program("stream-attachment-backup.py"),
        source_mount=source_mount,
    )
    consumer = attachment_command(
        runtime, args, destination, _program("restore-attachment-backup.py"),
        stage=stage, restore=True,
    )
    runtime.pipe(
        producer, consumer,
        source_env=runtime.stack_environment(args, source),
        destination_env=runtime.stack_environment(args, destination),
    )
    if destination == "local-rollback":
        runtime.run_stack(
            args, destination, "run", "--rm", "-T", "--no-deps", "--user", "0:0",
            "--volume", f"{stage}:{ATTACHMENT_CONTAINER_ROOT}", "--entrypoint", "sh",
            "attachment-init", "-ec", f"chown -R 65532:65532 {ATTACHMENT_CONTAINER_ROOT}",
        )


def stream_forward_releases(runtime: Runtime, args: argparse.Namespace, stage: str) -> None:
    destination = [
        *runtime.ssh_prefix(args),
        runtime.remote_shell(f"exec tar -xpf - -C {shlex.quote(stage)}"),
    ]
    runtime.send_tar(destination, args.local_release_root)


def stream_rollback_releases(runtime: Runtime, args: argparse.Namespace, stage: Path) -> None:
    source = [
        *runtime.ssh_prefix(args),
        runtime.remote_shell(
            f"exec tar -cpf - -C {shlex.quote(UNRAID_RELEASE_ROOT)} ."
        ),
    ]
    runtime.receive_release_tar(source, stage)


def release_inventory_at(
    runtime: Runtime, args: argparse.Namespace, location: str,
    stage: str | Path | None = None,
) -> dict[str, dict[str, object]]:
    if location == "local-production":
        return inventory.release_inventory(args.local_release_root)
    if location == "local-rollback":
        if stage is None:
            raise ValueError("rollback release inventory requires a staging path")
        return inventory.release_inventory(Path(stage))
    values = [
        "run", "--rm", "-T", "--no-deps", "--volume",
        f"{stage or UNRAID_RELEASE_ROOT}:{RELEASE_CONTAINER_ROOT}:ro",
    ]
    values.extend((
        "--entrypoint", "python", "backup-attachment-verifier", "-c",
        _inventory_program(), "releases", RELEASE_CONTAINER_ROOT,
    ))
    raw = runtime.run_stack(args, "unraid", *values, capture=True)
    return inventory.parse_release_inventory(raw)


def seal_staging(
    runtime: Runtime, args: argparse.Namespace, location: str,
    attachments: str | Path, releases: str | Path,
) -> None:
    """Apply immutable modes before whole-tree promotion."""

    if location == "unraid":
        quoted = shlex.quote(str(releases))
        script = (
            f"chown 65532:65532 {shlex.quote(str(attachments))}; "
            f"chmod 0750 {shlex.quote(str(attachments))}; "
            f"chown -R 0:0 {quoted}; "
            f"find {quoted} -type d -exec chmod 0555 {{}} +; "
            f"find {quoted} -type f -exec chmod 0444 {{}} +"
        )
        runtime.run([*runtime.ssh_prefix(args), runtime.remote_shell(script)])
        return
    for path in sorted(Path(releases).rglob("*"), reverse=True):
        path.chmod(0o555 if path.is_dir() else 0o444)
    Path(releases).chmod(0o555)


def promote_remote(
    runtime: Runtime, args: argparse.Namespace, attachments: str, releases: str,
    guard: target_state.TargetGuard,
) -> None:
    """Rename complete siblings and commit the target marker atomically."""

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
    runtime.run([
        *runtime.ssh_prefix(args),
        runtime.remote_shell(guards + promote + "; " + target_state.commit_script(guard)),
    ])


def promote_local(args: argparse.Namespace, attachments: Path, releases: Path) -> None:
    """Atomically rename complete staged trees into absent rollback paths."""

    root = safety.prove_rollback_root(args.rollback_root_guard)
    _validate_local_stage(root, attachments, ".attachments-migration-")
    _validate_local_stage(root, releases, ".releases-migration-")
    attachment_target = root / "attachments"
    release_target = root / "releases"
    if attachment_target.exists() or release_target.exists():
        raise RuntimeError("rollback destination paths must remain absent before promotion")
    safety.prove_rollback_root(args.rollback_root_guard)
    os.replace(attachments, attachment_target)
    try:
        safety.prove_rollback_root(args.rollback_root_guard)
        os.replace(releases, release_target)
    except BaseException:
        safety.prove_rollback_root(args.rollback_root_guard)
        os.replace(attachment_target, attachments)
        raise


def _validate_local_stage(root: Path, stage: Path, prefix: str) -> None:
    if (
        stage.parent.resolve() != root
        or not stage.name.startswith(prefix)
        or not stage.is_dir()
        or safety.has_reparse_boundary(stage)
    ):
        raise RuntimeError("rollback staging path identity is invalid")


def clean_rollback_destination(runtime: Runtime, args: argparse.Namespace) -> None:
    """Erase only the dedicated rollback project and allowlisted data children."""

    runtime.run_stack(args, "local-rollback", "down", "--volumes", "--remove-orphans")
    root = safety.prove_rollback_root(args.rollback_root_guard)
    children = tuple(root.iterdir())
    for child in children:
        resolved = child.resolve()
        if resolved.parent != root or safety.has_reparse_boundary(child):
            raise RuntimeError("rollback cleanup escaped the dedicated root")
        allowed = child.name in {"attachments", "releases"} or child.name.startswith(
            (".attachments-migration-", ".releases-migration-")
        )
        if not allowed:
            raise RuntimeError("rollback cleanup found an unexpected path")
    for child in children:
        safety.prove_rollback_root(args.rollback_root_guard)
        if child.is_dir() and not child.is_symlink():
            runtime.remove_tree(child)
        else:
            child.unlink()
