"""Backup and restore invariants for the fixed Unraid host."""

from __future__ import annotations

from pathlib import Path
import subprocess

import pytest

from infra.scripts.tests.unraid_test_support import (
    BASH,
    COMPOSE_PATH,
    SCRIPT_DIR,
    script,
)


def _run_pending_with_mocked_claim(
    tmp_path: Path, claim: str
) -> subprocess.CompletedProcess[str]:
    state = tmp_path / "claim-consumed"
    return subprocess.run(
        [
            str(BASH),
            "-c",
            r'''
source "$1"
claim="$2"
state="$3"

stack() {
  local argument quiet=false
  for argument in "$@"; do
    [[ "${argument}" == --quiet ]] && quiet=true
  done
  if [[ "$*" == *"printenv POSTGRES_USER"* ]]; then
    printf 'postgres\n'
  elif [[ "$*" == *"printenv POSTGRES_DB"* ]]; then
    printf 'little_orbit\n'
  elif [[ "$*" == *"psql"* ]]; then
    if [[ -n "${claim}" && ! -e "${state}" ]]; then
      : >"${state}"
      printf '%s\n' "${claim}"
      [[ "${quiet}" == true ]] || printf 'UPDATE 1\n'
    else
      [[ "${quiet}" == true ]] || printf 'UPDATE 0\n'
    fi
  else
    return 64
  fi
}

run_backup() { printf 'backup:%s\n' "$1"; }
run_restore_drill() { printf 'test_restore:%s\n' "$1"; }
run_pending
''',
            "pending-claim-test",
            (SCRIPT_DIR / "unraid-operations.sh").resolve().as_posix(),
            claim,
            state.resolve().as_posix(),
        ],
        check=False,
        capture_output=True,
        text=True,
        timeout=10,
    )


@pytest.mark.skipif(BASH is None, reason="a functioning Bash is unavailable")
def test_pending_runner_treats_an_empty_claim_as_no_work(tmp_path: Path) -> None:
    """psql's empty UPDATE command tag cannot become a malformed job claim."""

    result = _run_pending_with_mocked_claim(tmp_path, "")

    assert result.returncode == 0
    assert result.stdout == ""
    assert result.stderr == ""


@pytest.mark.skipif(BASH is None, reason="a functioning Bash is unavailable")
def test_pending_runner_dispatches_only_the_returned_claim_row(tmp_path: Path) -> None:
    """A command tag cannot contaminate the allowlisted kind after a real claim."""

    job_id = "12345678-1234-1234-1234-123456789abc"
    result = _run_pending_with_mocked_claim(tmp_path, f"{job_id}|backup")

    assert result.returncode == 0
    assert result.stdout == f"backup:{job_id}\n"
    assert result.stderr == ""


def test_gpu_lock_is_a_stable_root_owned_inode() -> None:
    """Shared consumers cannot silently substitute a link for the lock."""

    content = script("unraid-bootstrap.sh")
    assert '[[ ! -L "${lock_path}" ]]' in content
    assert "metadata=\"$(stat --format='%h:%s'" in content
    assert '"0:${GPU_GID}:660:1:0"' in content
    assert 'chmod 3770 "${GPU_ROOT}"' in content


def test_postgres_health_waits_for_final_tcp_server() -> None:
    """The one-shot role bootstrap cannot race the temporary init server."""

    content = COMPOSE_PATH.read_text(encoding="utf-8")
    assert "pg_isready -h 127.0.0.1" in content


def test_role_bootstrap_keeps_passwords_out_of_process_arguments() -> None:
    """Database role credentials enter psql through stdin-only variables."""

    content = COMPOSE_PATH.read_text(encoding="utf-8")
    extension = content.split("x-database-role-service:", maxsplit=1)[1].split(
        "\nservices:", maxsplit=1
    )[0]
    for variable in ("api", "worker", "media", "backup"):
        assert f"\\getenv {variable}_password POSTGRES_{variable.upper()}_PASSWORD" in extension
        assert f"--set={variable}_password" not in extension
    assert "} | psql --set=ON_ERROR_STOP=1" in extension


def test_backup_resumes_and_checks_every_exact_writer_before_success() -> None:
    """A backup cannot pass with a missing or unhealthy mutation service."""

    content = script("unraid-backup.sh")
    main = content.rsplit("main() {", maxsplit=1)[1]
    assert "readonly WRITER_SERVICES=(api worker media-worker)" in content
    assert "unraid_storage_ready" in content
    assert 'docker start "${writer_ids[@]}"' in content
    assert "{{.State.Health.Status}}" in content
    assert "|| true" not in content
    assert main.index("resume_writers") < main.index("jq -n --arg database")
    assert main.index("resume_writers") < main.index("write_pair_manifest")


def test_backup_and_restore_attachment_tools_cannot_mutate_live_bytes() -> None:
    """Backup reads are RO and the stream verifier receives no attachment mount."""

    compose = COMPOSE_PATH.read_text(encoding="utf-8")
    reader = compose.split("  backup-attachment-reader:", maxsplit=1)[1].split(
        "\n  backup-attachment-verifier:", maxsplit=1
    )[0]
    verifier = compose.split("  backup-attachment-verifier:", maxsplit=1)[1].split(
        "\n  database-bootstrap:", maxsplit=1
    )[0]
    backup = script("unraid-backup.sh")
    restore = script("unraid-restore-drill.sh")
    assert "/var/lib/little-orbit/attachments:ro" in reader
    assert 'user: "65532:65532"' in reader
    assert "read_only: true" in reader and "cap_drop:" in reader
    assert "volumes:" not in verifier
    assert 'user: "65532:65532"' in verifier
    assert "read_only: true" in verifier and "cap_drop:" in verifier
    assert "backup-attachment-reader" in backup
    assert "backup-attachment-verifier" in restore


def test_restore_database_is_networkless_read_only_and_tmpfs_only() -> None:
    """Decrypted database rows never enter the production cluster or durable storage."""

    compose = COMPOSE_PATH.read_text(encoding="utf-8")
    service = compose.split("  restore-drill-postgres:", maxsplit=1)[1].split(
        "\n  worker:", maxsplit=1
    )[0]
    restore = script("unraid-restore-drill.sh")
    assert 'user: "999:70"' in service
    assert "read_only: true" in service
    assert "cap_drop:" in service and "no-new-privileges:true" in service
    assert "/var/lib/postgresql/data:size=4g" in service
    assert "network_mode: none" in service
    assert "volumes:" not in service
    assert 'docker exec -i "${drill_container}" pg_restore' in restore
    assert "stack exec -T postgres pg_restore" not in restore


def test_backup_manifest_fences_schema_only_or_truncated_database_dumps() -> None:
    """The drill compares every retained table count to the frozen source."""

    backup = script("unraid-backup.sh")
    restore = script("unraid-restore-drill.sh")
    assert "capture_retained_table_counts" in backup
    assert "retained_table_counts:$retained_table_counts" in backup
    assert "schema_version:3" in backup
    assert ".schema_version == 3" in restore
    assert ".retained_table_counts" in restore
    assert "Restored retained-table counts do not match" in restore


def test_restore_requires_head_and_cleanup_before_success() -> None:
    """A drill pass proves head 0032 and destroys its isolated plaintext database."""

    content = script("unraid-restore-drill.sh")
    main = content.rsplit("main() {", maxsplit=1)[1]
    assert "(SELECT version_num FROM public.alembic_version) = '0032'" in content
    assert "unraid_storage_ready" in main
    assert "start_drill_database" in main
    assert '"none|true|999:70"' in content
    assert 'docker rm --force "${container}"' in content
    assert "|| true" not in content
    assert main.index("cleanup") < main.index("jq -n --arg pair_manifest_sha256")
    assert 'database_schema:"0032"' in content


def test_restore_evidence_records_exact_schema_head() -> None:
    """The operations ledger preserves the exact schema proof from the drill."""

    content = script("unraid-operations.sh")
    assert '"database_schema":"0032"' in content
    assert '"database_schema":"verified"' not in content
