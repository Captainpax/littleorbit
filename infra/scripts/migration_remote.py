"""Build the fixed, key-only remote commands used during direct migration."""

from __future__ import annotations

import argparse
import shlex

import migration_coordination as coordination


def ssh_prefix(args: argparse.Namespace) -> list[str]:
    return [
        "ssh", "-T", "-p", str(args.unraid_port), "-i", str(args.ssh_identity),
        "-o", "BatchMode=yes", "-o", "StrictHostKeyChecking=yes",
        "-o", "IdentitiesOnly=yes", "-o", "GlobalKnownHostsFile=NUL",
        "-o", "PasswordAuthentication=no", "-o", "KbdInteractiveAuthentication=no",
        "-o", "PreferredAuthentications=publickey", "-o", "ForwardAgent=no",
        "-o", "ForwardX11=no", "-o", "ClearAllForwardings=yes",
        "-o", "ProxyCommand=none", "-o", "PermitLocalCommand=no",
        "-o", "ConnectionAttempts=1", "-o", "ConnectTimeout=10",
        "-o", "ServerAliveInterval=15", "-o", "ServerAliveCountMax=4",
        "-o", f"UserKnownHostsFile={args.known_hosts}",
        f"{args.unraid_user}@{args.unraid_host}",
    ]


def remote_stack(args: argparse.Namespace, *values: str) -> str:
    command = " ".join(
        shlex.quote(item) for item in ("bash", args.unraid_stack, *values)
    )
    token = getattr(args, "migration_lock_token", None)
    if token is None:
        return command
    if len(token) != 64 or any(value not in "0123456789abcdef" for value in token):
        raise ValueError("migration lock token is invalid")
    return f"LITTLE_ORBIT_MIGRATION_LOCK_TOKEN={token} {command}"


def remote_shell(script: str) -> str:
    return f"sh -ec {shlex.quote(script)}"


def migration_remote_shell(args: argparse.Namespace, script: str) -> str:
    """Run a remote command while retaining this migration's shared flock."""

    token = getattr(args, "migration_lock_token", None)
    if not isinstance(token, str) or len(token) != 64 or any(
        value not in "0123456789abcdef" for value in token
    ):
        raise RuntimeError("migration lock capability is unavailable")
    values = (
        "exec", "bash", coordination.REMOTE_LOCK_HELPER, "run-migration", token,
        "sh", "-ec", script,
    )
    return " ".join(shlex.quote(value) for value in values)


def exclusive_remote_shell(script: str) -> str:
    """Run failure cleanup under the ordinary exclusive operations lock."""

    values = (
        "exec", "bash", coordination.REMOTE_LOCK_HELPER, "run-exclusive", "300",
        "sh", "-ec", script,
    )
    return " ".join(shlex.quote(value) for value in values)
