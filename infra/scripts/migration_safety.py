"""Fail-closed argument validation for the fixed Little Orbit host move."""

from __future__ import annotations

import argparse
from collections.abc import Mapping
from dataclasses import dataclass
import hmac
from io import BufferedReader
import json
import os
from pathlib import Path
import re
import socket
import stat
import subprocess


CRITICAL_ENVIRONMENT_KEYS = (
    "POSTGRES_DB",
    "POSTGRES_USER",
    "POSTGRES_PASSWORD",
    "POSTGRES_API_PASSWORD",
    "POSTGRES_WORKER_PASSWORD",
    "POSTGRES_MEDIA_PASSWORD",
    "POSTGRES_BACKUP_PASSWORD",
    "DATABASE_OWNER_URL",
    "DATABASE_API_URL",
    "DATABASE_WORKER_URL",
    "DATABASE_MEDIA_URL",
    "SESSION_SECRET",
    "TOKEN_PEPPER",
    "TOTP_ENCRYPTION_KEY",
    "OUTBOX_ENCRYPTION_KEY",
    "BACKUP_AGE_RECIPIENT",
    "SMTP_HOST",
    "SMTP_PORT",
    "SMTP_FROM",
    "SMTP_STARTTLS",
    "SMTP_USERNAME",
    "SMTP_PASSWORD",
)
AGE_RECIPIENT = re.compile(r"age1[0-9a-z]{20,100}")


@dataclass(frozen=True)
class ProvenLocalSecrets:
    """Exact bytes whose source provenance was verified before target writes."""

    environment: bytes
    backup_identity: bytes | None


@dataclass(frozen=True)
class PinnedDirectory:
    path: Path
    device: int
    inode: int


def capture_open_file(
    handle: BufferedReader, path: Path,
) -> tuple[bytes, tuple[int, int, int, int]]:
    """Capture bytes and stable file identity while retaining the open handle."""

    descriptor = os.fstat(handle.fileno())
    path_status = path.stat()
    identity = (
        descriptor.st_dev, descriptor.st_ino, descriptor.st_size,
        descriptor.st_mtime_ns,
    )
    if identity != (
        path_status.st_dev, path_status.st_ino, path_status.st_size,
        path_status.st_mtime_ns,
    ):
        raise RuntimeError("local secret file identity changed during preflight")
    value = handle.read()
    if not value:
        raise RuntimeError("local secret file is empty")
    return value, identity


def prove_open_file_unchanged(
    handle: BufferedReader, path: Path, expected: bytes,
    identity: tuple[int, int, int, int],
) -> None:
    """Reject replacement or edits while provenance checks used the path."""

    descriptor = os.fstat(handle.fileno())
    path_status = path.stat()
    current_identity = (
        descriptor.st_dev, descriptor.st_ino, descriptor.st_size,
        descriptor.st_mtime_ns,
    )
    path_identity = (
        path_status.st_dev, path_status.st_ino, path_status.st_size,
        path_status.st_mtime_ns,
    )
    handle.seek(0)
    current = handle.read()
    if (
        current_identity != identity
        or path_identity != identity
        or not hmac.compare_digest(current, expected)
    ):
        raise RuntimeError("local secret file changed during preflight")


def _validate_common(
    args: argparse.Namespace, *, legacy_host: str, unraid_host: str, unraid_port: int,
) -> None:
    if args.local_host != legacy_host or args.unraid_host != unraid_host:
        raise ValueError(f"hosts must be {legacy_host} and {unraid_host}")
    if args.unraid_port != unraid_port:
        raise ValueError(f"Unraid SSH port must be {unraid_port}")
    for path in (args.ssh_identity, args.known_hosts, args.local_env):
        if not path.is_file():
            raise ValueError(f"required file is unavailable: {path}")


def has_reparse_boundary(path: Path) -> bool:
    junction = getattr(path, "is_junction", lambda: False)()
    attributes = getattr(path.lstat(), "st_file_attributes", 0)
    return path.is_symlink() or junction or bool(
        attributes & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0)
    )


def _allowed_rollback_child(path: Path) -> bool:
    return path.name in {"attachments", "releases"} or path.name.startswith(
        (".attachments-migration-", ".releases-migration-")
    )


def _canonical_rollback_root(root: Path | None) -> tuple[Path, Path]:
    if root is None or not root.is_absolute() or not root.is_dir():
        raise ValueError("rollback data root must be an existing absolute directory")
    if has_reparse_boundary(root):
        raise ValueError("rollback data root cannot be a reparse point")
    resolved = root.resolve()
    if resolved != root.absolute():
        raise ValueError("rollback data root must use its canonical path")
    return root, resolved


def _validate_rollback_children(root: Path, *, require_empty: bool) -> None:
    children = tuple(root.iterdir())
    if require_empty and children:
        raise ValueError("rollback data root must be empty")
    if not require_empty and any(not _allowed_rollback_child(path) for path in children):
        raise ValueError("rollback recovery root contains an unexpected path")


def pin_rollback_root(root: Path | None, *, require_empty: bool) -> PinnedDirectory:
    root, resolved = _canonical_rollback_root(root)
    workspace = Path.cwd().resolve()
    forbidden = {workspace, Path.home().resolve(), Path(resolved.anchor), workspace.parent}
    if resolved in forbidden or workspace in resolved.parents:
        raise ValueError("rollback data root is too broad")
    _validate_rollback_children(root, require_empty=require_empty)
    status = root.stat()
    return PinnedDirectory(resolved, status.st_dev, status.st_ino)


def prove_rollback_root(guard: PinnedDirectory) -> Path:
    root = guard.path
    if not root.is_dir() or has_reparse_boundary(root) or root.resolve() != root:
        raise RuntimeError("rollback data root identity changed")
    status = root.stat()
    if (status.st_dev, status.st_ino) != (guard.device, guard.inode):
        raise RuntimeError("rollback data root identity changed")
    return root


def _validate_forward(args: argparse.Namespace) -> None:
    if args.backup_identity is None or not args.backup_identity.is_file():
        raise ValueError("forward migration requires the backup identity")
    root = args.local_release_root
    if args.rollback_data_root is not None or root.is_symlink() or not root.is_dir():
        raise ValueError("forward migration arguments are inconsistent")
    if not any(
        path.is_file() and not path.is_symlink() and path.stat().st_size > 0
        for path in root.rglob("*.apk")
    ):
        raise ValueError("forward migration requires a nonempty immutable APK root")


def _validate_rollback(args: argparse.Namespace) -> None:
    if args.backup_identity is not None:
        raise ValueError("rollback never transfers or replaces backup identity")
    guard = pin_rollback_root(args.rollback_data_root, require_empty=True)
    args.rollback_data_root = guard.path
    args.rollback_root_guard = guard


def _validate_recovery(args: argparse.Namespace) -> None:
    if args.backup_identity is not None:
        raise ValueError("interrupted recovery never transfers a backup identity")
    if args.direction == "recover-forward":
        if args.rollback_data_root is not None:
            raise ValueError("forward recovery cannot use a rollback data root")
        return
    guard = pin_rollback_root(args.rollback_data_root, require_empty=False)
    args.rollback_data_root = guard.path
    args.rollback_root_guard = guard


def validate_arguments(
    args: argparse.Namespace, *, confirmations: dict[str, str], legacy_host: str,
    unraid_host: str, unraid_port: int,
) -> None:
    """Validate direction, identity pins, secrets, and destination isolation."""

    _validate_common(
        args, legacy_host=legacy_host, unraid_host=unraid_host, unraid_port=unraid_port,
    )
    if args.confirm != confirmations[args.direction]:
        raise ValueError("confirmation does not match the selected direction")
    if args.direction == "forward":
        _validate_forward(args)
    elif args.direction == "rollback":
        _validate_rollback(args)
    else:
        _validate_recovery(args)


def require_routed_local_host(
    expected: str, peer: str, peer_port: int, *, observed: str | None = None,
) -> None:
    """Refuse a production stream unless its route originates on the fixed source host."""

    if observed is None:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as probe:
            probe.connect((peer, peer_port))
            observed = str(probe.getsockname()[0])
    if observed != expected:
        raise ValueError(
            f"migration must run on {expected}; the route to {peer} uses {observed}"
        )


def compose_service_environment(raw: str, service: str) -> dict[str, str]:
    """Extract one rendered Compose environment with content-free failures."""

    try:
        document = json.loads(raw)
    except (json.JSONDecodeError, TypeError) as error:
        raise RuntimeError("rendered local environment is invalid") from error
    if not isinstance(document, dict):
        raise RuntimeError("rendered local environment is invalid")
    services = document.get("services")
    definition = services.get(service) if isinstance(services, dict) else None
    environment = definition.get("environment") if isinstance(definition, dict) else None
    if not isinstance(environment, dict):
        raise RuntimeError("rendered local environment is unavailable")
    values: dict[str, str] = {}
    for name, value in environment.items():
        if not isinstance(name, str) or not isinstance(value, str):
            raise RuntimeError("rendered local environment is invalid")
        values[name] = value
    return values


def _service_environment(
    environments: Mapping[str, Mapping[str, str]], service: str,
) -> Mapping[str, str]:
    value = environments.get(service)
    if value is None:
        raise RuntimeError("running source environment evidence is unavailable")
    return value


def _match_environment_keys(
    expected: Mapping[str, str], observed: Mapping[str, str], names: tuple[str, ...],
    *, incomplete: str, mismatch: str,
) -> None:
    for name in names:
        value = expected.get(name)
        current = observed.get(name)
        if value is None:
            raise RuntimeError(incomplete)
        if current is None or not hmac.compare_digest(value, current):
            raise RuntimeError(mismatch)


def prove_critical_environment_provenance(
    candidate: Mapping[str, Mapping[str, str]],
    running: Mapping[str, Mapping[str, str]],
) -> str:
    """Prove stable secret/config values match every running source process."""

    for service in ("api", "worker"):
        _match_environment_keys(
            _service_environment(candidate, service),
            _service_environment(running, service),
            CRITICAL_ENVIRONMENT_KEYS,
            incomplete="critical local environment is incomplete",
            mismatch="critical local environment does not match the source",
        )
    for service in ("api", "worker", "media-worker"):
        _match_environment_keys(
            _service_environment(candidate, service),
            _service_environment(running, service),
            ("DATABASE_URL",),
            incomplete="effective source database environment does not match",
            mismatch="effective source database environment does not match",
        )
    _match_environment_keys(
        _service_environment(candidate, "postgres"),
        _service_environment(running, "postgres"),
        ("POSTGRES_DB", "POSTGRES_USER", "POSTGRES_PASSWORD"),
        incomplete="effective source database environment does not match",
        mismatch="effective source database environment does not match",
    )
    return candidate["api"]["BACKUP_AGE_RECIPIENT"]


def prove_age_identity_recipient(
    identity: Path, expected: str,
) -> None:
    """Derive the supplied age identity's recipient and compare it in memory."""

    try:
        result = subprocess.run(
            ["age-keygen", "-y", str(identity)],
            check=False,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
    except OSError as error:
        raise RuntimeError("age-keygen is unavailable for identity verification") from error
    recipient = result.stdout.strip()
    if (
        result.returncode != 0
        or len(result.stdout.splitlines()) != 1
        or AGE_RECIPIENT.fullmatch(recipient) is None
    ):
        raise RuntimeError("backup age identity could not be verified")
    if not hmac.compare_digest(recipient, expected):
        raise RuntimeError("backup age identity does not match the source recipient")
