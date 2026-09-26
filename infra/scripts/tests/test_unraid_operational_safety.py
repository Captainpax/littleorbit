"""Static invariants for the fixed Unraid host entry points."""

from __future__ import annotations

from pathlib import Path


SCRIPT_DIR = Path(__file__).resolve().parents[1]
COMPOSE_PATH = SCRIPT_DIR.parent / "compose.yaml"


def script(name: str) -> str:
    """Read one checked-in host script."""

    return (SCRIPT_DIR / name).read_text(encoding="utf-8")


def test_bootstrap_requires_exact_unraid_mounts() -> None:
    """Root-filesystem lookalike directories cannot receive live state."""

    content = script("unraid-bootstrap.sh")
    assert "mountpoint --quiet --" in content
    assert "--output TARGET,SOURCE,FSTYPE" in content
    assert "require_unraid_mount /mnt/cache device btrfs" in content
    assert "require_unraid_mount /mnt/user shfs fuse.shfs" in content


def test_startup_waits_for_exact_mount_identities() -> None:
    """The reboot path applies the same mount identity boundary."""

    content = script("unraid-user-script.sh")
    assert '"/mnt/cache /dev/"*" btrfs"' in content
    assert '"/mnt/user shfs fuse.shfs"' in content
    assert "until runtime_mounts_ready && docker info" in content


def test_startup_rechecks_exposure_and_stops_gateway_on_failure() -> None:
    """The gateway cannot remain published after a failed post-start boundary check."""

    content = script("unraid-user-script.sh")
    start = content.split("start_stack_fail_closed() {", maxsplit=1)[1]
    assert start.count('bash "${SCRIPT_DIR}/unraid-firewall.sh"') >= 1
    assert start.count("stop_gateway_after_failed_startup") >= 2
    assert 'stop gateway' in content


def test_gpu_lock_is_a_stable_root_owned_inode() -> None:
    """Shared consumers cannot silently substitute a link for the lock."""

    content = script("unraid-bootstrap.sh")
    assert '[[ ! -L "${lock_path}" ]]' in content
    assert 'metadata="$(stat --format=\'%h:%s\'' in content
    assert '"0:${GPU_GID}:660:1:0"' in content
    assert 'chmod 3770 "${GPU_ROOT}"' in content


def test_postgres_health_waits_for_final_tcp_server() -> None:
    """The one-shot role bootstrap cannot race the temporary init server."""

    content = COMPOSE_PATH.read_text(encoding="utf-8")
    assert "pg_isready -h 127.0.0.1" in content


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


def test_restore_requires_head_and_cleanup_before_success() -> None:
    """A drill pass proves head 0032 and absence of its plaintext database."""

    content = script("unraid-restore-drill.sh")
    main = content.rsplit("main() {", maxsplit=1)[1]
    assert "(SELECT version_num FROM public.alembic_version) = '0032'" in content
    assert "unraid_storage_ready" in main
    assert "remove_stale_drill_databases" in main
    assert "Refusing to remove an active restore-drill database" in content
    assert "|| true" not in content
    assert main.index("cleanup") < main.index("jq -n --arg pair_manifest_sha256")
    assert 'database_schema:"0032"' in content


def test_restore_evidence_records_exact_schema_head() -> None:
    """The operations ledger preserves the exact schema proof from the drill."""

    content = script("unraid-operations.sh")
    assert '\"database_schema\":\"0032\"' in content
    assert '\"database_schema\":\"verified\"' not in content
