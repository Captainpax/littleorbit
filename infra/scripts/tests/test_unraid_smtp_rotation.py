"""Focused safety tests for the Unraid Gmail app-password rotation helper."""

from __future__ import annotations

from pathlib import Path
import subprocess

import pytest

from infra.scripts.tests.unraid_test_support import (
    BASH,
    COMPOSE_PATH,
    SCRIPT_DIR,
    run_bash,
    script,
)


ROTATION_SCRIPT = "unraid-rotate-smtp-password.sh"


def runtime_env(password: str = "oldpasswordvalue") -> str:
    """Return one synthetic Gmail environment without any live credential."""

    return (
        "PUBLIC_BASE_URL=https://example.invalid\n"
        "SMTP_HOST=smtp.gmail.com\n"
        "SMTP_PORT=587\n"
        "SMTP_STARTTLS=true\n"
        "SMTP_USERNAME=tester@example.invalid\n"
        f"SMTP_PASSWORD={password}\n"
        "REGISTRATION_OPEN=false\n"
    )


def sourced(command: str, *arguments: str) -> subprocess.CompletedProcess[str]:
    """Source the helper and run a synthetic function-level probe."""

    helper = (SCRIPT_DIR / ROTATION_SCRIPT).resolve().as_posix()
    return run_bash(f'source "$1"; {command}', helper, *arguments)


@pytest.mark.skipif(BASH is None, reason="a functioning Bash is unavailable")
def test_render_replaces_exactly_one_password_and_preserves_other_values(
    tmp_path: Path,
) -> None:
    """The atomic candidate changes only the intended environment definition."""

    source = tmp_path / "runtime.env"
    destination = tmp_path / "candidate.env"
    source.write_text(runtime_env(), encoding="utf-8")
    destination.touch()

    result = sourced(
        'NEW_PASSWORD="newpasswordvalue"; render_rotated_env "$2" "$3"',
        source.resolve().as_posix(),
        destination.resolve().as_posix(),
    )

    assert result.returncode == 0, result.stderr
    expected = runtime_env("newpasswordvalue")
    assert destination.read_text(encoding="utf-8") == expected
    assert destination.read_text(encoding="utf-8").count("SMTP_PASSWORD=") == 1


@pytest.mark.skipif(BASH is None, reason="a functioning Bash is unavailable")
@pytest.mark.parametrize(
    "content",
    [
        runtime_env().replace("SMTP_PASSWORD=oldpasswordvalue\n", ""),
        runtime_env() + "SMTP_PASSWORD=duplicatevalue1\n",
    ],
)
def test_render_rejects_missing_or_duplicate_password_key(
    tmp_path: Path, content: str
) -> None:
    """An ambiguous environment can never be installed."""

    source = tmp_path / "runtime.env"
    destination = tmp_path / "candidate.env"
    source.write_text(content, encoding="utf-8")
    destination.touch()

    result = sourced(
        'NEW_PASSWORD="newpasswordvalue"; render_rotated_env "$2" "$3"',
        source.resolve().as_posix(),
        destination.resolve().as_posix(),
    )

    assert result.returncode != 0


@pytest.mark.skipif(BASH is None, reason="a functioning Bash is unavailable")
@pytest.mark.parametrize(
    ("value", "accepted"),
    [
        (b"abcdefghijklmnop", True),
        (b"abcdefghijklmnop\n", True),
        (b"abcd efgh ijkl\n", False),
        (b"abcdefghijklmnop\nsecond\n", False),
        (b"SMTP_PASSWORD=x\n", False),
    ],
)
def test_password_input_is_one_bounded_gmail_value(
    tmp_path: Path, value: bytes, accepted: bool
) -> None:
    """Newlines, grouping spaces, and dotenv injection are rejected."""

    password_file = tmp_path / "password"
    password_file.write_bytes(value)
    result = sourced(
        'read_password_file "$2"', password_file.resolve().as_posix()
    )
    assert (result.returncode == 0) is accepted


@pytest.mark.skipif(BASH is None, reason="a functioning Bash is unavailable")
def test_cli_never_accepts_the_password_as_an_argument() -> None:
    """Only a protected filename or standard input may select secret input."""

    result = sourced(
        "if parse_cli rotate plaintext-secret; then exit 1; fi; "
        "parse_cli rotate --stdin; [[ \"$INPUT_MODE\" == stdin ]]; "
        "parse_cli rotate --password-file /protected/input; "
        "[[ \"$INPUT_MODE\" == file && \"$INPUT_PATH\" == /protected/input ]]"
    )
    assert result.returncode == 0, result.stderr


def test_rotation_uses_fixed_paths_lock_and_protected_input() -> None:
    """Production paths and the root-only source boundary cannot be overridden."""

    content = script(ROTATION_SCRIPT)
    main = content.split("main() {", maxsplit=1)[1]
    load = content.split("load_new_password() {", maxsplit=1)[1].split(
        "\n}", maxsplit=1
    )[0]

    assert 'SECRET_ROOT="/mnt/cache/little-orbit-secrets"' in content
    assert 'ENV_FILE="${SECRET_ROOT}/runtime.env"' in content
    assert 'source "${SCRIPT_DIR}/unraid-operation-lock.sh"' in content
    assert main.index("acquire_little_orbit_operations_lock wait 300") < main.index(
        "require_target"
    )
    assert "fix_little_orbit_local_docker_endpoint" in main
    assert "secure_file \"${path}\"" in load
    assert "stat -c '%u:%g:%a:%h'" in content
    assert "stat -c '%F:%u:%g:%a:%h'" not in content
    assert "head -c 18" in content
    assert "SMTP password rotation refuses shell tracing." in content


@pytest.mark.skipif(BASH is None, reason="a functioning Bash is unavailable")
def test_zero_byte_secure_stage_does_not_depend_on_stat_type_wording(
    tmp_path: Path,
) -> None:
    """GNU's `regular empty file` label cannot reject a safe new staging file."""

    stage = tmp_path / "empty-stage"
    trace = tmp_path / "stat-format"
    result = sourced(
        'trace="$3"; chown() { :; }; chmod() { :; }; '
        'stat() { printf "%s" "$2" >"$trace"; printf "0:0:600:1\\n"; }; '
        'create_secure_empty "$2"; [[ -f "$2" && ! -s "$2" ]]',
        stage.resolve().as_posix(),
        trace.resolve().as_posix(),
    )

    assert result.returncode == 0, result.stderr
    assert trace.read_text(encoding="utf-8") == "%u:%g:%a:%h"


def test_runtime_replacement_is_durable_and_preserves_root_only_metadata() -> None:
    """The candidate is synced before one rename and the directory is synced after."""

    content = script(ROTATION_SCRIPT)
    copy = content.split("create_secure_copy() {", maxsplit=1)[1].split(
        "\n}", maxsplit=1
    )[0]
    atomic = content.split("atomic_replace_runtime_from() {", maxsplit=1)[1].split(
        "\n}", maxsplit=1
    )[0]

    assert 'chown 0:0 "${destination}"' in copy
    assert 'chmod 0600 "${destination}"' in copy
    assert 'sync -f "${destination}"' in copy
    assert atomic.index("create_secure_copy") < atomic.index("mv -T")
    assert atomic.index("mv -T") < atomic.index('sync -f "${SECRET_ROOT}"')
    assert "secure_file \"${ENV_FILE}\"" in atomic


def test_only_worker_is_recreated_and_readiness_is_mandatory() -> None:
    """SMTP rotation cannot restart an unrelated production service."""

    content = script(ROTATION_SCRIPT)
    stop = content.split("stop_worker_fail_closed() {", maxsplit=1)[1].split(
        "\n}", maxsplit=1
    )[0]
    recreate = content.split("recreate_worker() {", maxsplit=1)[1].split(
        "\n}", maxsplit=1
    )[0]

    assert "stack stop --timeout 30 worker" in stop
    assert "--no-deps --force-recreate --wait --wait-timeout 300 worker" in recreate
    assert "service_is_healthy" in recreate
    compose = COMPOSE_PATH.read_text(encoding="utf-8")
    worker = compose.split("  worker:", maxsplit=1)[1].split(
        "\n  context-fetcher:", maxsplit=1
    )[0]
    assert "healthcheck:" in worker
    assert "little_orbit_api.worker" in worker
    assert "('postgres', 5432)" in worker
    for service in ("gateway", "api", "web", "media-worker", "postgres"):
        assert service not in stop
        assert service not in recreate


@pytest.mark.skipif(BASH is None, reason="a functioning Bash is unavailable")
def test_readiness_failure_runs_fail_closed_rollback(tmp_path: Path) -> None:
    """A failed new worker is stopped and the old environment is restored."""

    trace = tmp_path / "trace"
    result = sourced(
        'trace="$2"; record() { printf "%s\\n" "$1" >>"$trace"; }; '
        'prepare_new_rotation() { ROTATION_ID=0123456789abcdef0123456789abcdef; '
        'ROTATION_ACTIVE=true; ROLLBACK_ARMED=true; record prepare; }; '
        'stop_worker_fail_closed() { record stop; }; '
        'atomic_replace_runtime_from() { record replace; }; '
        'stack() { record "stack:$*"; }; '
        'recreate_worker() { record readiness-failed; return 70; }; '
        'write_journal() { record "journal:$1"; }; '
        'perform_rollback() { record rollback; }; '
        'cleanup_all_staging() { record cleanup-all; }; '
        'cleanup_transient() { record cleanup-transient; }; '
        'cleanup_input() { record cleanup-input; }; '
        'trap finish EXIT; execute_rotation file ignored',
        trace.resolve().as_posix(),
    )

    assert result.returncode == 70
    assert trace.read_text(encoding="utf-8").splitlines() == [
        "prepare",
        "stop",
        "replace",
        "stack:validate",
        "readiness-failed",
        "rollback",
        "cleanup-all",
        "cleanup-input",
    ]
    assert '"outcome":"rolled_back"' in result.stderr


@pytest.mark.skipif(BASH is None, reason="a functioning Bash is unavailable")
def test_rollback_rerun_recovers_durable_rolled_back_state(tmp_path: Path) -> None:
    """A crash after the terminal journal resumes cleanup instead of wedging."""

    trace = tmp_path / "trace"
    result = sourced(
        'trace="$2"; load_journal() { JOURNAL_STATE=rolled-back; '
        'ROTATION_ID=0123456789abcdef0123456789abcdef; }; '
        'recover_rolled_back_staging() { printf "recover\n" >>"$trace"; }; '
        "rollback_rotation",
        trace.resolve().as_posix(),
    )

    assert result.returncode == 0, result.stderr
    assert trace.read_text(encoding="utf-8").splitlines() == ["recover"]
    assert '"outcome":"rolled_back"' in result.stdout


@pytest.mark.skipif(BASH is None, reason="a functioning Bash is unavailable")
def test_rolled_back_recovery_proves_snapshot_before_owned_cleanup(
    tmp_path: Path,
) -> None:
    """The old snapshot must match runtime before fixed staging is removed."""

    trace = tmp_path / "trace"
    result = sourced(
        'trace="$2"; record() { printf "%s\n" "$1" >>"$trace"; }; '
        'stage_exists() { [[ "$1" == "$OLD_ENV_PATH" '
        '|| "$1" == "$NEW_ENV_PATH" ]]; }; '
        'stage_has_content() { [[ "$1" == "$OLD_ENV_PATH" ]]; }; '
        'secure_file() { record "secure:${1##*/}"; }; '
        'validate_smtp_layout() { record "validate:${1##*/}"; }; '
        'cmp() { record compare; }; cleanup_all_staging() { record cleanup; }; '
        'all_staging_is_absent() { record absent; }; recover_rolled_back_staging',
        trace.resolve().as_posix(),
    )

    assert result.returncode == 0, result.stderr
    assert trace.read_text(encoding="utf-8").splitlines() == [
        "secure:runtime.env",
        "validate:runtime.env",
        "secure:.smtp-password-rotation.old.env",
        "validate:.smtp-password-rotation.old.env",
        "compare",
        "cleanup",
        "absent",
    ]


@pytest.mark.skipif(BASH is None, reason="a functioning Bash is unavailable")
def test_recovery_accepts_old_snapshot_interrupted_after_truncate(
    tmp_path: Path,
) -> None:
    """An empty old stage is safe only after transient cleanup completed."""

    trace = tmp_path / "trace"
    result = sourced(
        'trace="$2"; record() { printf "%s\n" "$1" >>"$trace"; }; '
        'stage_exists() { [[ "$1" == "$OLD_ENV_PATH" ]]; }; '
        'stage_has_content() { return 1; }; secure_file() { record secure; }; '
        'validate_smtp_layout() { record validate; }; '
        'cleanup_all_staging() { record cleanup; }; '
        'all_staging_is_absent() { record absent; }; recover_rolled_back_staging',
        trace.resolve().as_posix(),
    )

    assert result.returncode == 0, result.stderr
    assert trace.read_text(encoding="utf-8").splitlines() == [
        "secure", "validate", "secure", "cleanup", "absent",
    ]


@pytest.mark.skipif(BASH is None, reason="a functioning Bash is unavailable")
def test_recovery_refuses_impossible_or_unsafe_residual_staging(
    tmp_path: Path,
) -> None:
    """Missing rollback proof plus a transient stage can never report success."""

    trace = tmp_path / "trace"
    result = sourced(
        'trace="$2"; stage_exists() { [[ "$1" == "$NEW_ENV_PATH" ]]; }; '
        'secure_file() { :; }; validate_smtp_layout() { :; }; '
        'cleanup_all_staging() { printf "cleanup\n" >>"$trace"; }; '
        "recover_rolled_back_staging",
        trace.resolve().as_posix(),
    )

    assert result.returncode == 78
    assert not trace.exists()


@pytest.mark.skipif(BASH is None, reason="a functioning Bash is unavailable")
def test_failed_rolled_back_recovery_emits_no_success_outcome() -> None:
    """Unsafe leftovers make the retry fail without an ambiguous success record."""

    result = sourced(
        'load_journal() { JOURNAL_STATE=rolled-back; '
        'ROTATION_ID=0123456789abcdef0123456789abcdef; }; '
        'prove_rolled_back_runtime() { :; }; cleanup_all_staging() { :; }; '
        'all_staging_is_absent() { return 1; }; rollback_rotation'
    )

    assert result.returncode == 78
    assert '"outcome"' not in result.stdout
    assert "inconsistent or unsafe" in result.stderr


def test_success_waits_for_operator_test_before_discarding_rollback() -> None:
    """Worker readiness alone cannot erase the old local credential snapshot."""

    content = script(ROTATION_SCRIPT)
    execute = content.split("execute_rotation() {", maxsplit=1)[1].split(
        "\n}", maxsplit=1
    )[0]
    commit = content.split("commit_rotation() {", maxsplit=1)[1].split(
        "\n}", maxsplit=1
    )[0]
    rollback = content.split("rollback_steps() {", maxsplit=1)[1].split(
        "\n}", maxsplit=1
    )[0]
    perform = content.split("perform_rollback() {", maxsplit=1)[1].split(
        "\n}", maxsplit=1
    )[0]

    assert execute.index("stop_worker_fail_closed") < execute.index(
        "atomic_replace_runtime_from"
    )
    assert execute.index("recreate_worker") < execute.index(
        "write_journal awaiting-test"
    )
    assert "OLD_ENV_PATH" not in execute
    assert commit.index("require_live_worker") < commit.index(
        "write_journal committed"
    )
    assert commit.index("write_journal committed") < commit.rindex(
        'remove_secure_stage "${OLD_ENV_PATH}"'
    )
    assert rollback.index("stop_worker_fail_closed") < rollback.index(
        "atomic_replace_runtime_from"
    )
    assert rollback.index("atomic_replace_runtime_from") < rollback.index(
        "recreate_worker"
    )
    assert "if stop_worker_fail_closed" in perform
    assert "final worker stop could not be verified" in perform


def test_helper_neither_sends_mail_nor_revokes_google_credentials() -> None:
    """Provider testing and old-password revocation remain explicit human actions."""

    content = script(ROTATION_SCRIPT).lower()
    forbidden = ("smtp.login", "smtplib", "sendmail", "send_message", "accounts.google")
    assert all(value not in content for value in forbidden)
