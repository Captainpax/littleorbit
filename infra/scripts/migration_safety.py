"""Fail-closed argument validation for the fixed Little Orbit host move."""

from __future__ import annotations

import argparse
from pathlib import Path
import socket


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


def _validate_rollback_root(root: Path | None) -> None:
    if root is None or not root.is_absolute() or not root.is_dir():
        raise ValueError("rollback data root must be an existing absolute directory")
    resolved = root.resolve()
    workspace = Path.cwd().resolve()
    forbidden = {workspace, Path.home().resolve(), Path(resolved.anchor), workspace.parent}
    if resolved in forbidden or workspace in resolved.parents:
        raise ValueError("rollback data root is too broad")
    if any(root.iterdir()):
        raise ValueError("rollback data root must be empty")


def _validate_forward(args: argparse.Namespace) -> None:
    if args.backup_identity is None or not args.backup_identity.is_file():
        raise ValueError("forward migration requires the backup identity")
    if args.rollback_data_root is not None or not args.local_release_root.is_dir():
        raise ValueError("forward migration arguments are inconsistent")


def _validate_rollback(args: argparse.Namespace) -> None:
    if args.backup_identity is not None:
        raise ValueError("rollback never transfers or replaces backup identity")
    _validate_rollback_root(args.rollback_data_root)


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
    else:
        _validate_rollback(args)


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
