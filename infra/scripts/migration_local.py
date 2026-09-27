"""Pinned local Docker and secret provenance boundaries for direct migration."""

from __future__ import annotations

import argparse
from collections.abc import Callable
from contextlib import ExitStack
from pathlib import Path
import os
import subprocess

import migration_artifacts as artifacts
import migration_safety as safety


LOCAL_DOCKER_HOST = "npipe:////./pipe/docker_engine"
ROLLBACK_PROJECT = "little-orbit-rollback"
ROLLBACK_VOLUME = f"{ROLLBACK_PROJECT}_postgres-data"
LOCAL_ENV_ALLOWLIST = frozenset({
    "APPDATA", "COMMONPROGRAMFILES", "COMMONPROGRAMFILES(X86)", "COMSPEC",
    "HOME", "HOMEDRIVE", "HOMEPATH", "LOCALAPPDATA", "PATH", "PATHEXT",
    "PROCESSOR_ARCHITECTURE", "PROGRAMDATA", "PROGRAMFILES",
    "PROGRAMFILES(X86)", "SYSTEMROOT", "TEMP", "TMP", "USERPROFILE", "WINDIR",
})


def local_docker_environment(args: argparse.Namespace) -> dict[str, str]:
    """Pin local operations to the default named pipe without ambient controls."""

    values = {
        name: value for name, value in os.environ.items()
        if name.upper() in LOCAL_ENV_ALLOWLIST
    }
    values["DOCKER_HOST"] = LOCAL_DOCKER_HOST
    values["LITTLE_ORBIT_ENV_FILE"] = str(args.local_env.resolve())
    return values


def rollback_environment(args: argparse.Namespace) -> dict[str, str]:
    values = local_docker_environment(args)
    values["ROLLBACK_DATA_ROOT"] = str(args.rollback_data_root.resolve())
    values["ROLLBACK_GATEWAY_BIND_ADDRESS"] = "127.0.0.1"
    values["ROLLBACK_GATEWAY_PORT"] = "18181"
    values["GATEWAY_INTERNAL_SUBNET"] = "10.253.182.0/28"
    values["GATEWAY_CADDY_IP"] = "10.253.182.2"
    values["GATEWAY_API_IP"] = "10.253.182.3"
    return values


def local_production_stack(args: argparse.Namespace, *values: str) -> list[str]:
    return [
        "docker", "compose", "--project-name", "little-orbit",
        "--env-file", str(args.local_env.resolve()), "-f",
        str(Path(__file__).resolve().parents[1] / "compose.yaml"), *values,
    ]


def local_rollback_stack(args: argparse.Namespace, *values: str) -> list[str]:
    return [
        "docker", "compose", "--project-name", ROLLBACK_PROJECT,
        "--env-file", str(args.local_env.resolve()), "-f",
        str(Path(__file__).resolve().parents[1] / "compose.yaml"), "-f",
        str(Path(__file__).resolve().parents[1] / "compose.rollback.yaml"), *values,
    ]


def assert_local_release_mount(
    args: argparse.Namespace, run: Callable[..., str],
    run_stack: Callable[..., str],
) -> None:
    """Prove the supplied immutable root is the running API's read-only bind."""

    container = run_stack(args, "local-production", "ps", "-q", "api", capture=True)
    if not 12 <= len(container) <= 64 or "\n" in container or not all(
        character in "0123456789abcdef" for character in container.lower()
    ):
        raise RuntimeError("source API container identity is ambiguous")
    raw = run([
        "docker", "inspect", "--format",
        "{{range .Mounts}}{{if eq .Destination \"/var/lib/little-orbit/releases\"}}"
        "{{.Source}}|{{.RW}}{{println}}{{end}}{{end}}",
        container,
    ], capture=True, env=local_docker_environment(args))
    entries = [line for line in raw.splitlines() if line]
    if len(entries) != 1 or "|" not in entries[0]:
        raise RuntimeError("source API release mount is unavailable")
    source, writable = entries[0].rsplit("|", maxsplit=1)
    if Path(source).resolve() != args.local_release_root.resolve() or writable != "false":
        raise RuntimeError("local release root is not the source API read-only mount")


def assert_local_production_stopped(
    args: argparse.Namespace, run: Callable[..., str],
) -> None:
    running = run([
        "docker", "ps", "--filter", "label=com.docker.compose.project=little-orbit",
        "--format", "{{.ID}}",
    ], capture=True, env=local_docker_environment(args))
    if running:
        raise RuntimeError("the old little-orbit project must be completely stopped")


def assert_fresh_rollback_project(
    args: argparse.Namespace, run: Callable[..., str],
) -> None:
    environment = local_docker_environment(args)
    containers = run([
        "docker", "ps", "-aq", "--filter",
        f"label=com.docker.compose.project={ROLLBACK_PROJECT}",
    ], capture=True, env=environment)
    if containers:
        raise RuntimeError("rollback project already has containers")
    result = subprocess.run(
        ["docker", "volume", "inspect", ROLLBACK_VOLUME], text=True,
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, env=environment,
    )
    if result.returncode == 0:
        raise RuntimeError("rollback PostgreSQL volume already exists")


def prove_local_environment_provenance(
    args: argparse.Namespace, source: str, run: Callable[..., str],
    artifact_runtime: artifacts.Runtime,
) -> safety.ProvenLocalSecrets:
    """Bind supplied local env and age identity bytes to the running source."""

    with ExitStack() as files:
        env_handle = files.enter_context(args.local_env.open("rb"))
        environment, env_status = safety.capture_open_file(env_handle, args.local_env)
        identity_path: Path | None = args.backup_identity
        identity_handle = None
        identity: bytes | None = None
        identity_status: tuple[int, int, int, int] | None = None
        if args.direction == "forward":
            if identity_path is None:
                raise RuntimeError("forward backup identity is unavailable")
            identity_handle = files.enter_context(identity_path.open("rb"))
            identity, identity_status = safety.capture_open_file(
                identity_handle, identity_path,
            )
        rendered = run(
            local_production_stack(args, "config", "--format", "json"),
            capture=True, env=local_docker_environment(args),
        )
        services = ("api", "worker", "media-worker", "postgres")
        candidate = {
            service: safety.compose_service_environment(rendered, service)
            for service in services
        }
        observed = {
            service: artifacts.container_environment(
                artifact_runtime, args, source, service,
            )
            for service in services
        }
        recipient = safety.prove_critical_environment_provenance(candidate, observed)
        if identity_path is not None:
            safety.prove_age_identity_recipient(identity_path, recipient)
        safety.prove_open_file_unchanged(
            env_handle, args.local_env, environment, env_status,
        )
        if (
            identity_handle is not None and identity_path is not None
            and identity is not None and identity_status
        ):
            safety.prove_open_file_unchanged(
                identity_handle, identity_path, identity, identity_status,
            )
    return safety.ProvenLocalSecrets(environment, identity)
