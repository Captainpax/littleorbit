"""Transactional database-role rotation invariants for the fixed Unraid host."""

from __future__ import annotations

from pathlib import Path

import pytest

from infra.scripts.tests.unraid_test_support import BASH, run_bash, script


ROTATION_SCRIPT = "unraid-rotate-database-roles.sh"
SCRIPT_PATH = Path(__file__).resolve().parents[1] / ROTATION_SCRIPT
PASSWORDS = {
    "POSTGRES_API_PASSWORD": "a" * 64,
    "POSTGRES_WORKER_PASSWORD": "b" * 64,
    "POSTGRES_MEDIA_PASSWORD": "c" * 64,
    "POSTGRES_BACKUP_PASSWORD": "d" * 64,
}


def runtime_env() -> str:
    """Return a representative root-only environment without real credentials."""

    return """# preserved comment
POSTGRES_DB=little_orbit
POSTGRES_USER=little_orbit
POSTGRES_PASSWORD=owner-kept-byte-for-byte
POSTGRES_API_PASSWORD=old-api
POSTGRES_WORKER_PASSWORD=old-worker
POSTGRES_MEDIA_PASSWORD=old-media
POSTGRES_BACKUP_PASSWORD=old-backup
DATABASE_OWNER_URL=postgresql+asyncpg://little_orbit:owner-kept-byte-for-byte@postgres:5432/little_orbit
DATABASE_API_URL=postgresql+asyncpg://little_orbit_api:old-api@postgres:5432/little_orbit
DATABASE_WORKER_URL=postgresql+asyncpg://little_orbit_worker:old-worker@postgres:5432/little_orbit
DATABASE_MEDIA_URL=postgresql+asyncpg://little_orbit_media:old-media@postgres:5432/little_orbit
SMTP_HOST=example.invalid
"""


def sourced(command: str, *arguments: str):  # type: ignore[no-untyped-def]
    """Source the guarded script, then run one focused Bash probe."""

    return run_bash(
        'source "$1"; ' + command,
        SCRIPT_PATH.resolve().as_posix(),
        *arguments,
    )


def test_rotation_scope_and_secret_transport_are_exact() -> None:
    """Only four child roles rotate, and credentials never enter process argv."""

    content = script(ROTATION_SCRIPT)
    replacement = content.split("replacement_line() {", maxsplit=1)[1].split(
        "\n}", maxsplit=1
    )[0]
    probe = content.split("credential_connects() {", maxsplit=1)[1].split(
        "\n}", maxsplit=1
    )[0]
    assert "openssl rand -hex 32" in content
    assert "Database-role rotation refuses shell tracing" in content
    assert "POSTGRES_PASSWORD" not in replacement
    assert "DATABASE_OWNER_URL" not in replacement
    assert replacement.count("POSTGRES_") == 7
    assert all(key in replacement for key in PASSWORDS)
    assert all(key in replacement for key in (
        "DATABASE_API_URL", "DATABASE_WORKER_URL", "DATABASE_MEDIA_URL",
    ))
    assert "printf '%s\\n' \"${password}\" | stack exec -T postgres" in probe
    assert "PGPASSWORD" in probe and "--no-password" in probe
    assert "--host=postgres" in probe and "--host=127.0.0.1" not in probe
    assert "service DNS crosses the SCRAM boundary" in probe
    assert "--set=api_password" not in probe and "--set=worker_password" not in probe
    assert "-e PGPASSWORD" not in probe


@pytest.mark.skipif(BASH is None, reason="a functioning Bash is unavailable")
def test_zero_byte_secure_stage_can_be_created_and_cleaned(tmp_path: Path) -> None:
    """An empty regular staging inode is valid before secret bytes are copied."""

    stage = tmp_path / "empty-stage"
    result = sourced(
        'chown() { :; }; chmod() { :; }; sync() { :; }; '
        'stat() { printf "0:0:600:1\\n"; }; '
        'create_secure_empty "$2"; secure_file "$2"; '
        'remove_secure_stage "$2"; [[ ! -e "$2" && ! -L "$2" ]]',
        stage.resolve().as_posix(),
    )
    assert result.returncode == 0, result.stderr
    assert not stage.exists()


@pytest.mark.skipif(BASH is None, reason="a functioning Bash is unavailable")
def test_runtime_env_replaces_seven_child_keys_and_preserves_owner(
    tmp_path: Path,
) -> None:
    """Rotation rewrites matching URLs while leaving owner and unrelated bytes alone."""

    source = tmp_path / "runtime.env"
    destination = tmp_path / "rotated.env"
    source.write_text(runtime_env(), encoding="utf-8")
    destination.touch()
    assignments = " ".join(
        f'NEW_PASSWORDS[{key}]="${index}"'
        for index, key in enumerate(PASSWORDS, start=4)
    )
    result = sourced(
        f"{assignments}; render_rotated_env \"$2\" \"$3\"",
        source.resolve().as_posix(),
        destination.resolve().as_posix(),
        *PASSWORDS.values(),
    )
    assert result.returncode == 0, result.stderr
    rendered = destination.read_text(encoding="utf-8")
    assert "POSTGRES_PASSWORD=owner-kept-byte-for-byte\n" in rendered
    assert (
        "DATABASE_OWNER_URL=postgresql+asyncpg://little_orbit:"
        "owner-kept-byte-for-byte@postgres:5432/little_orbit\n"
    ) in rendered
    assert "# preserved comment\n" in rendered
    assert "SMTP_HOST=example.invalid\n" in rendered
    for key, value in PASSWORDS.items():
        assert f"{key}={value}\n" in rendered
    for role, value in zip(("api", "worker", "media"), PASSWORDS.values()):
        assert (
            f"DATABASE_{role.upper()}_URL=postgresql+asyncpg://"
            f"little_orbit_{role}:{value}@postgres:5432/little_orbit\n"
        ) in rendered


@pytest.mark.skipif(BASH is None, reason="a functioning Bash is unavailable")
def test_runtime_env_rewrite_rejects_duplicate_child_key(tmp_path: Path) -> None:
    """A second matching definition cannot hide a stale credential."""

    source = tmp_path / "runtime.env"
    destination = tmp_path / "rotated.env"
    source.write_text(
        runtime_env() + "POSTGRES_API_PASSWORD=duplicate\n", encoding="utf-8"
    )
    destination.touch()
    assignments = "; ".join(
        f"NEW_PASSWORDS[{key}]={'abcd'[index] * 64}"
        for index, key in enumerate(PASSWORDS)
    )
    result = sourced(
        f"{assignments}; render_rotated_env \"$2\" \"$3\"",
        source.resolve().as_posix(),
        destination.resolve().as_posix(),
    )
    assert result.returncode == 78


@pytest.mark.skipif(BASH is None, reason="a functioning Bash is unavailable")
def test_credentials_reach_database_probe_only_through_stdin(tmp_path: Path) -> None:
    """Neither a database URL nor a role password is placed in a child argument."""

    arguments = tmp_path / "arguments"
    fake_secret = "not-a-real-secret-value"
    result = sourced(
        'args_path="$2"; secret="$3"; '
        'read_env_value_from() { printf "%s" "$secret"; }; '
        'stack() { printf "%s\\n" "$*" >"$args_path"; IFS= read -r piped; '
        '[[ "$piped" == "$secret" ]]; }; '
        "credential_connects ignored POSTGRES_API_PASSWORD little_orbit_api little_orbit",
        arguments.resolve().as_posix(),
        fake_secret,
    )
    assert result.returncode == 0, result.stderr
    assert fake_secret not in arguments.read_text(encoding="utf-8")
    assert fake_secret not in result.stdout and fake_secret not in result.stderr


@pytest.mark.skipif(BASH is None, reason="a functioning Bash is unavailable")
def test_old_role_probes_are_new_old_rejected_new(tmp_path: Path) -> None:
    """An unrelated connection failure cannot masquerade as old-password rejection."""

    trace = tmp_path / "trace"
    error = tmp_path / "probe-error"
    result = sourced(
        'trace="$2"; error_path="$3"; OLD_ENV="old-env"; '
        'read_env_value_from() { printf little_orbit; }; '
        'mktemp() { : >"$error_path"; printf "%s" "$error_path"; }; '
        'chown() { :; }; chmod() { :; }; '
        'credential_connects() { if [[ "$1" == "old-env" ]]; then '
        'printf "password authentication failed for user \\"%s\\"\\n" "$3" >&2; '
        'printf "old:%s\\n" "$3" >>"$trace"; return 2; fi; '
        'printf "new:%s\\n" "$3" >>"$trace"; }; verify_old_credentials_rejected',
        trace.resolve().as_posix(),
        error.resolve().as_posix(),
    )
    assert result.returncode == 0, result.stderr
    roles = ("api", "worker", "media", "backup")
    assert trace.read_text(encoding="utf-8").splitlines() == [
        event
        for role in roles
        for event in (f"new:little_orbit_{role}", f"old:little_orbit_{role}",
                      f"new:little_orbit_{role}")
    ]


@pytest.mark.skipif(BASH is None, reason="a functioning Bash is unavailable")
def test_rotation_orders_commit_after_firewall_and_gateway(tmp_path: Path) -> None:
    """The gateway opens only after internal credential proofs and firewall prepare."""

    trace = tmp_path / "trace"
    result = sourced(
        'trace="$2"; record() { printf "%s\\n" "$1" >>"$trace"; }; '
        'prepare_new_rotation() { ROTATION_ID=0123456789abcdef0123456789abcdef; '
        'OLD_ENV=old; NEW_ENV=new; record prepare; }; '
        'write_journal() { record "journal:$1"; }; stop_rotation_services() { record stop; }; '
        'atomic_replace_runtime_from() { record replace; }; '
        'stack() { record "stack:$*"; }; bootstrap_roles() { record bootstrap; }; '
        'recreate_internal_services() { record recreate; }; '
        'verify_credentials_accept() { record new-accepted; }; '
        'verify_old_credentials_rejected() { record old-rejected; }; '
        'start_gateway_fail_closed() { record gateway; }; cleanup_staging() { record cleanup; }; '
        "execute_rotation",
        trace.resolve().as_posix(),
    )
    assert result.returncode == 0, result.stderr
    events = trace.read_text(encoding="utf-8").splitlines()
    assert events == [
        "prepare", "journal:preparing", "stop", "replace", "stack:validate",
        "bootstrap", "recreate", "new-accepted", "old-rejected", "gateway",
        "journal:committed", "cleanup",
    ]
    assert '"outcome":"rotated"' in result.stdout


@pytest.mark.skipif(BASH is None, reason="a functioning Bash is unavailable")
def test_precommit_gateway_failure_runs_rollback(tmp_path: Path) -> None:
    """A failure after gateway start remains inside the rollback boundary."""

    trace = tmp_path / "trace"
    result = sourced(
        'trace="$2"; record() { printf "%s\\n" "$1" >>"$trace"; }; '
        'prepare_new_rotation() { ROTATION_ID=0123456789abcdef0123456789abcdef; '
        'OLD_ENV=old; NEW_ENV=new; }; write_journal() { record "journal:$1"; }; '
        'stop_rotation_services() { record stop; }; atomic_replace_runtime_from() { :; }; '
        'stack() { :; }; bootstrap_roles() { :; }; recreate_internal_services() { :; }; '
        'verify_credentials_accept() { :; }; verify_old_credentials_rejected() { :; }; '
        'start_gateway_fail_closed() { record gateway-failed; return 69; }; '
        'perform_rollback() { record rollback; return 0; }; '
        'cleanup_staging() { record cleanup; }; trap finish EXIT; execute_rotation',
        trace.resolve().as_posix(),
    )
    assert result.returncode == 69
    assert trace.read_text(encoding="utf-8").splitlines() == [
        "journal:preparing", "stop", "gateway-failed", "rollback", "cleanup",
    ]
    assert '"outcome":"rolled_back"' in result.stderr


@pytest.mark.skipif(BASH is None, reason="a functioning Bash is unavailable")
def test_postcommit_cleanup_failure_never_rolls_back(tmp_path: Path) -> None:
    """Once committed, residue cleanup cannot rotate healthy credentials backward."""

    trace = tmp_path / "trace"
    result = sourced(
        'trace="$2"; record() { printf "%s\\n" "$1" >>"$trace"; }; '
        'prepare_new_rotation() { ROTATION_ID=0123456789abcdef0123456789abcdef; '
        'OLD_ENV=old; NEW_ENV=new; }; write_journal() { record "journal:$1"; }; '
        'stop_rotation_services() { :; }; atomic_replace_runtime_from() { :; }; '
        'stack() { :; }; bootstrap_roles() { :; }; recreate_internal_services() { :; }; '
        'verify_credentials_accept() { :; }; verify_old_credentials_rejected() { :; }; '
        'start_gateway_fail_closed() { :; }; perform_rollback() { record rollback; }; '
        'cleanup_staging() { record cleanup-failed; return 73; }; '
        "trap finish EXIT; execute_rotation",
        trace.resolve().as_posix(),
    )
    assert result.returncode == 70
    events = trace.read_text(encoding="utf-8").splitlines()
    assert events[:2] == ["journal:preparing", "journal:committed"]
    assert events.count("cleanup-failed") == 2
    assert "rollback" not in events


def test_recovery_journal_and_atomic_file_boundaries_are_durable() -> None:
    """A crash leaves fixed recovery material, while the marker remains secret-free."""

    content = script(ROTATION_SCRIPT)
    journal = content.split("write_journal() {", maxsplit=1)[1].split(
        "\n}", maxsplit=1
    )[0]
    atomic = content.split("atomic_replace_runtime_from() {", maxsplit=1)[1].split(
        "\n}", maxsplit=1
    )[0]
    main = content.split("main() {", maxsplit=1)[1]
    assert ".database-role-rotation.old.env" in content
    assert ".database-role-rotation.new.env" in content
    assert ".database-role-rotation.runtime.env" in content
    assert "schema=1\\noperation_id=%s\\nstate=%s" in journal
    assert "PASSWORD" not in journal and "DATABASE_" not in journal
    assert journal.index('sync -f "${temporary}"') < journal.index("mv -T")
    assert "create_secure_copy" in atomic and "mv -T" in atomic
    assert atomic.index("mv -T") < atomic.index('sync -f "${SECRET_ROOT}"')
    assert main.index("acquire_little_orbit_operations_lock") < main.index(
        "require_target"
    )
    assert '"${JOURNAL_STATE}" != preparing' in content
    assert 'write_journal rolled-back' in content


def test_rollback_proves_old_internal_state_before_opening_gateway() -> None:
    """Recovery cannot publish a gateway over unverified old credentials."""

    content = script(ROTATION_SCRIPT)
    rollback = content.split("rollback_steps() {", maxsplit=1)[1].split(
        "\n}", maxsplit=1
    )[0]
    assert rollback.index("stop_rotation_services") < rollback.index(
        "atomic_replace_runtime_from"
    )
    assert rollback.index("bootstrap_roles") < rollback.index(
        "recreate_internal_services"
    )
    assert rollback.index("verify_credentials_accept") < rollback.index(
        "start_gateway_fail_closed"
    )
    assert rollback.index("start_gateway_fail_closed") < rollback.index(
        "write_journal rolled-back"
    )
