"""Argument, transport, environment, and secret-boundary migration tests."""

from __future__ import annotations

import argparse
from pathlib import Path
import shlex
import subprocess

import pytest

from infra.scripts.tests.direct_migration_test_support import (
    MODULE,
    RECOVERY_CONFIRMATIONS,
    arguments,
    recovery_arguments,
)


def test_validation_rejects_any_other_host(tmp_path: Path) -> None:
    value = arguments(tmp_path)
    value.unraid_host = "192.168.50.15"
    with pytest.raises(ValueError, match="hosts must be"):
        MODULE.validate_arguments(value)


def test_runtime_route_must_originate_on_fixed_legacy_host() -> None:
    MODULE.safety.require_routed_local_host(
        "192.168.50.182", "192.168.50.14", 23, observed="192.168.50.182"
    )
    with pytest.raises(ValueError, match="must run on 192.168.50.182"):
        MODULE.safety.require_routed_local_host(
            "192.168.50.182", "192.168.50.14", 23, observed="192.168.50.99"
        )


def test_direction_requires_unmistakable_confirmation(tmp_path: Path) -> None:
    value = arguments(tmp_path, "rollback")
    value.confirm = MODULE.CONFIRMATIONS["forward"]
    with pytest.raises(ValueError, match="confirmation"):
        MODULE.validate_arguments(value)


@pytest.mark.parametrize("direction", tuple(RECOVERY_CONFIRMATIONS))
def test_recovery_direction_requires_its_exact_confirmation(
    tmp_path: Path, direction: str,
) -> None:
    expected = RECOVERY_CONFIRMATIONS[direction]
    assert MODULE.CONFIRMATIONS[direction] == expected
    value = recovery_arguments(tmp_path, direction)
    MODULE.validate_arguments(value)
    value.confirm = expected + "-mistyped"
    with pytest.raises(ValueError, match="confirmation"):
        MODULE.validate_arguments(value)


def test_forward_requires_fixed_root_identity_and_nonempty_apk(tmp_path: Path) -> None:
    value = arguments(tmp_path)
    value.unraid_user = "operator"
    with pytest.raises(ValueError, match="root user"):
        MODULE.validate_arguments(value)
    value.unraid_user = "root"
    next(value.local_release_root.iterdir()).unlink()
    with pytest.raises(ValueError, match="nonempty immutable APK"):
        MODULE.validate_arguments(value)


def test_rollback_rejects_secret_transfer_and_nonempty_root(tmp_path: Path) -> None:
    value = arguments(tmp_path, "rollback")
    value.backup_identity = tmp_path / "backup-age-identity.txt"
    with pytest.raises(ValueError, match="never transfers"):
        MODULE.validate_arguments(value)
    value.backup_identity = None
    (value.rollback_data_root / "old").write_text("stale", encoding="utf-8")
    with pytest.raises(ValueError, match="must be empty"):
        MODULE.validate_arguments(value)


def test_cli_has_no_archive_output_option() -> None:
    actions = {action.dest: action for action in MODULE.parser()._actions}
    destinations = set(actions)
    assert "direction" in destinations
    assert set(actions["direction"].choices) == {
        "forward", "rollback", "recover-forward", "recover-rollback",
    }
    assert "output" not in destinations
    assert "archive" not in destinations


def test_compound_remote_commands_use_fail_fast_shell() -> None:
    assert shlex.split(MODULE.remote_shell("false; true")) == ["sh", "-ec", "false; true"]


def test_ssh_is_key_only_pinned_and_forwarding_disabled(tmp_path: Path) -> None:
    command = MODULE.ssh_prefix(arguments(tmp_path))
    joined = " ".join(command)
    for option in (
        "StrictHostKeyChecking=yes", "IdentitiesOnly=yes", "PasswordAuthentication=no",
        "KbdInteractiveAuthentication=no", "ClearAllForwardings=yes",
    ):
        assert option in joined


def test_forward_runtime_override_fixes_unraid_network_gpu_and_ai_settings(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    captured: list[tuple[bytes, str, bytes]] = []

    def capture(
        _args: argparse.Namespace, source: bytes, target: str, suffix: bytes = b""
    ) -> None:
        captured.append((source, target, suffix))

    monkeypatch.setattr(MODULE, "stream_secret", capture)
    MODULE.transfer_forward_secrets(
        arguments(tmp_path),
        MODULE.safety.ProvenLocalSecrets(b"fixture-env", b"fixture-identity"),
    )
    runtime_suffix = captured[0][2]
    expected = {
        b"PUBLIC_BASE_URL": b"https://lil-orb.pax-kun.com",
        b"GATEWAY_BIND_ADDRESS": b"192.168.50.14",
        b"GATEWAY_INTERNAL_SUBNET": b"10.253.14.0/28",
        b"GATEWAY_CADDY_IP": b"10.253.14.2",
        b"GATEWAY_API_IP": b"10.253.14.3",
        b"TRUSTED_PROXY_IP": b"10.253.14.2",
        b"GPU_LOCK_HOST_PATH": b"/mnt/cache/gpu-coordinator/gpu.lock",
        b"AI_SCHEDULE_TIMEZONE": b"America/Los_Angeles",
        b"AI_LEARNING_LOCAL_HOUR": b"1",
        b"AI_GENERATION_LOCAL_HOUR": b"3",
        b"AI_WORK_RETRY_HOURS": b"6",
        b"AI_WORK_MAX_RUNTIME_SECONDS": b"6600",
        b"AI_COVERAGE_DAYS": b"14",
    }
    resolved = dict(
        line.split(b"=", maxsplit=1)
        for line in runtime_suffix.splitlines()
        if b"=" in line
    )
    for key, value in expected.items():
        assert resolved[key] == value
    assert captured[1][1] == MODULE.UNRAID_BACKUP_IDENTITY


def test_secret_transfer_rejects_links_and_insecure_existing_files(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    captured: list[list[str]] = []

    def capture(
        command: list[str], _source: bytes, _suffix: bytes = b"", **_kwargs: object,
    ) -> None:
        captured.append(command)

    monkeypatch.setattr(MODULE.transport, "send_file", capture)
    value = arguments(tmp_path)
    value.migration_lock_token = "d" * 64
    MODULE.stream_secret(value, value.local_env.read_bytes(), MODULE.UNRAID_ENV)
    remote = captured[0][-1]
    assert f"test ! -L {MODULE.UNRAID_SECRET_ROOT}" in remote
    assert "stat -c" in remote
    assert "= 0:0:700" in remote
    assert f"test ! -L {MODULE.UNRAID_ENV}" in remote
    assert "regular file:0:0:600:1" in remote


def test_runtime_environment_rebuild_replaces_overrides_once() -> None:
    source = (
        b"PUBLIC_BASE_URL=https://old.example\r\n"
        b"SECRET_VALUE=preserved-verbatim\r\n"
        b"export TRUSTED_PROXY_IP=172.30.14.2\n"
    )
    overrides = (
        b"PUBLIC_BASE_URL=https://lil-orb.pax-kun.com\n"
        b"TRUSTED_PROXY_IP=10.253.14.2\n"
    )
    rebuilt = MODULE.transport.rebuild_environment(source, overrides)
    assert rebuilt.count(b"PUBLIC_BASE_URL=") == 1
    assert rebuilt.count(b"TRUSTED_PROXY_IP=") == 1
    assert b"SECRET_VALUE=preserved-verbatim\r\n" in rebuilt
    assert b"https://old.example" not in rebuilt


def test_local_docker_environment_drops_ambient_controls_and_pins_daemon(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("COMPOSE_PROFILES", "tools")
    monkeypatch.setenv("COMPOSE_FILE", "attacker.yaml")
    monkeypatch.setenv("DOCKER_CONTEXT", "remote")
    monkeypatch.setenv("DOCKER_HOST", "tcp://remote.example:2375")
    monkeypatch.setenv("SESSION_SECRET", "ambient-secret-must-not-win")
    monkeypatch.setenv("DATABASE_API_URL", "postgresql://ambient")
    value = arguments(tmp_path)
    environment = MODULE.local_docker_environment(value)
    assert environment["DOCKER_HOST"] == MODULE.LOCAL_DOCKER_HOST
    assert environment["LITTLE_ORBIT_ENV_FILE"] == str(value.local_env.resolve())
    assert "COMPOSE_PROFILES" not in environment
    assert "COMPOSE_FILE" not in environment
    assert "DOCKER_CONTEXT" not in environment
    assert "SESSION_SECRET" not in environment
    assert "DATABASE_API_URL" not in environment


def test_critical_env_must_match_every_running_source_without_value_leak() -> None:
    shared = {
        name: f"private-fixture-{index}"
        for index, name in enumerate(MODULE.safety.CRITICAL_ENVIRONMENT_KEYS)
    }
    candidate = {
        "api": dict(shared, DATABASE_URL="postgresql://api"),
        "worker": dict(shared, DATABASE_URL="postgresql://worker"),
        "media-worker": {"DATABASE_URL": "postgresql://media"},
        "postgres": {
            "POSTGRES_DB": "little_orbit", "POSTGRES_USER": "little_orbit",
            "POSTGRES_PASSWORD": "private-postgres-fixture",
        },
    }
    observed = {service: dict(values) for service, values in candidate.items()}
    assert (
        MODULE.safety.prove_critical_environment_provenance(candidate, observed)
        == shared["BACKUP_AGE_RECIPIENT"]
    )
    observed["worker"]["SESSION_SECRET"] = "different-private-fixture"
    with pytest.raises(RuntimeError) as raised:
        MODULE.safety.prove_critical_environment_provenance(candidate, observed)
    message = str(raised.value)
    assert "private-fixture" not in message
    assert "different-private-fixture" not in message


def test_age_identity_recipient_is_derived_and_compared_in_memory(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    identity = tmp_path / "identity.txt"
    identity.write_text("AGE-SECRET-KEY-FIXTURE", encoding="utf-8")
    recipient = "age1" + "q" * 58
    monkeypatch.setattr(
        MODULE.safety.subprocess, "run",
        lambda *_args, **_kwargs: subprocess.CompletedProcess(
            ["age-keygen"], 0, stdout=f"{recipient}\n", stderr="",
        ),
    )
    MODULE.safety.prove_age_identity_recipient(identity, recipient)
    with pytest.raises(RuntimeError) as raised:
        MODULE.safety.prove_age_identity_recipient(identity, "age1" + "p" * 58)
    assert recipient not in str(raised.value)
