"""Runtime, network, and lock invariants for the fixed Unraid host."""

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


def test_startup_waits_for_exact_mount_identities() -> None:
    """The reboot path applies the same mount identity boundary."""

    content = script("unraid-user-script.sh")
    assert '"/mnt/cache /dev/"*" btrfs"' in content
    assert '"/mnt/user shfs fuse.shfs"' in content
    assert "until runtime_mounts_ready && docker info" in content


def test_pacific_schedules_require_exact_configured_and_effective_timezone() -> None:
    """Installation and wall-clock execution both fail closed on timezone drift."""

    helper = script("unraid-timezone.sh")
    installer = script("unraid-install-user-scripts.sh")
    dispatcher = script("unraid-user-script.sh")
    require_target = installer.split("require_target() {", maxsplit=1)[1].split(
        "\n}", maxsplit=1
    )[0]
    scheduled_branch = dispatcher.split("backup|test_restore)", maxsplit=1)[1].split(
        ";;", maxsplit=1
    )[0]

    assert 'LITTLE_ORBIT_SCHEDULE_TIMEZONE="America/Los_Angeles"' in helper
    assert "/boot/config/ident.cfg" in helper
    assert 'cmp -s -- "${localtime_path}" "${zoneinfo_path}"' in helper
    assert 'source "${SOURCE_DIR}/unraid-timezone.sh"' in installer
    assert "require_unraid_pacific_timezone" in require_target
    assert 'source "${SCRIPT_DIR}/unraid-timezone.sh"' in dispatcher
    assert "require_unraid_pacific_timezone" in scheduled_branch
    assert installer.rindex("require_target") < installer.rindex(
        "install_wrapper little-orbit-startup"
    )


@pytest.mark.skipif(BASH is None, reason="a functioning Bash is unavailable")
def test_timezone_guard_accepts_only_matching_identifier_and_zoneinfo(
    tmp_path: Path,
) -> None:
    """The shared guard rejects both configured-name and effective-file mismatch."""

    helper = SCRIPT_DIR / "unraid-timezone.sh"
    config = tmp_path / "ident.cfg"
    localtime = tmp_path / "localtime"
    zoneinfo = tmp_path / "America_Los_Angeles"
    zoneinfo.write_bytes(b"test-zoneinfo\n")
    localtime.write_bytes(zoneinfo.read_bytes())

    def check() -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [
                str(BASH),
                "-c",
                'source "$1"; require_unraid_pacific_timezone "$2" "$3" "$4"',
                "timezone-test",
                helper.resolve().as_posix(),
                config.resolve().as_posix(),
                localtime.resolve().as_posix(),
                zoneinfo.resolve().as_posix(),
            ],
            check=False,
            capture_output=True,
            text=True,
            timeout=10,
        )

    config.write_bytes(b'timeZone="America/Los_Angeles"\r\n')
    assert check().returncode == 0

    config.write_text('timeZone="UTC"\n', encoding="utf-8")
    mismatch = check()
    assert mismatch.returncode == 78
    assert "America/Los_Angeles" in mismatch.stderr

    config.write_text('timeZone="America/Los_Angeles"\n', encoding="utf-8")
    localtime.write_bytes(b"different-zoneinfo\n")
    effective_mismatch = check()
    assert effective_mismatch.returncode == 78
    assert "effective host timezone" in effective_mismatch.stderr


def test_startup_rechecks_exposure_and_stops_gateway_on_failure() -> None:
    """The gateway cannot remain published after a failed post-start boundary check."""

    content = script("unraid-user-script.sh")
    unraid = (COMPOSE_PATH.parent / "compose.unraid.yaml").read_text(encoding="utf-8")
    gateway = unraid.split("  gateway:", maxsplit=1)[1].split("\n\n  api:", maxsplit=1)[0]
    assert 'restart: "no"' in gateway
    assert "on-failure" not in gateway
    start = content.split("start_stack_fail_closed() {", maxsplit=1)[1]
    assert start.count('bash "${SCRIPT_DIR}/unraid-firewall.sh"') >= 1
    assert start.count("stop_gateway_after_failed_startup") >= 2
    assert "com.docker.compose.project=little-orbit" in content
    assert "com.docker.compose.service=gateway" in content
    assert 'docker stop "${gateway_ids[@]}"' in content


def test_firewall_scopes_original_and_reply_conntrack_directions() -> None:
    """The port guard accepts NPM replies without bypassing unrelated rules."""

    content = script("unraid-firewall.sh")
    assert "--ctstate ESTABLISHED,RELATED --ctdir REPLY" in content
    assert '--ctorigsrc "${PROXY_ADDRESS}"' in content
    assert content.count("--ctdir ORIGINAL") == 2
    assert content.index("--ctdir REPLY") < content.index("--ctdir ORIGINAL")
    assert 'readonly EXPECTED_ADDRESS="192.168.50.14"' in content
    assert 'readonly PROXY_ADDRESS="192.168.50.6"' in content
    assert "verify_exact_ipv4_listener" in content
    assert '"${EXPECTED_ADDRESS}:${PUBLISHED_PORT}"' in content
    assert "verify_running_exposure_model" in content
    assert "com.docker.compose.project=little-orbit" in content
    assert '.HostConfig.PortBindings == {' in content
    assert '[[ "${MODE}" == verify || "${MODE}" == --prepare ]]' in content


def test_backup_recipient_accepts_crlf_environment_files() -> None:
    """A Windows-origin runtime env cannot poison the age recipient value."""

    function = script("unraid-backup.sh").split("read_recipient() {", maxsplit=1)[1]
    function = function.split("\n}", maxsplit=1)[0]
    assert "tr -d '\\r'" in function


def test_compose_validation_is_quiet_and_secret_safe() -> None:
    """Operators can validate interpolation without printing expanded secrets."""

    launcher = script("unraid-stack.sh")
    assert '"${1:-}" == "validate"' in launcher
    assert "set -- config --quiet" in launcher
    assert "require_fixed_setting GATEWAY_BIND_ADDRESS 192.168.50.14" in launcher
    assert (
        "require_fixed_setting LITTLE_ORBIT_DATA_ROOT /mnt/cache/little-orbit-live"
        in launcher
    )
    assert (
        "require_fixed_setting GPU_LOCK_HOST_PATH /mnt/cache/gpu-coordinator/gpu.lock"
        in launcher
    )
    assert 'unset "${RUNTIME_ENV_KEYS[@]}"' in launcher
    assert "sanitize_process_environment" in launcher
    assert (
        "LITTLE_ORBIT_MIGRATION_LOCK_TOKEN|LITTLE_ORBIT_OPERATIONS_LOCK_FD"
        in launcher
    )
    assert "inventory_runtime_keys" in launcher
    assert "unset COMPOSE_FILE COMPOSE_PROJECT_NAME COMPOSE_PATH_SEPARATOR" in launcher
    assert "COMPOSE_PROFILES" in launcher and "COMPOSE_ENV_FILES" in launcher
    assert "reject_runtime_control_keys" in launcher
    assert "export DOCKER_HOST=unix:///var/run/docker.sock" in launcher
    assert "unset DOCKER_CONTEXT" in launcher
    assert "-S /var/run/docker.sock" in launcher
    assert "verify_effective_exposure_model" in launcher
    assert 'config --format json | jq -e' in launcher
    assert '$ports[0].port.host_ip == $address' in launcher
    assert '"regular file:0:0:600:1"' in launcher


def test_every_stateful_leaf_uses_the_shared_operations_mutex() -> None:
    """Direct leaf calls cannot race the dispatcher or a migration run."""

    helper = script("unraid-operation-lock.sh")
    dispatcher = script("unraid-operations.sh")
    backup = script("unraid-backup.sh")
    restore = script("unraid-restore-drill.sh")
    startup = script("unraid-user-script.sh")
    bootstrap = script("unraid-bootstrap.sh")
    firewall = script("unraid-firewall.sh")
    installer = script("unraid-install-user-scripts.sh")
    stack = script("unraid-stack.sh")
    rotation = script("unraid-rotate-database-roles.sh")
    assert '"/var/lock/little-orbit-operations.lock"' in helper
    assert "LITTLE_ORBIT_OPERATIONS_LOCK_FD" in helper
    assert "flock --wait" in helper and "flock --nonblock" in helper
    for content in (dispatcher, backup, restore):
        assert 'source "${SCRIPT_DIR}/unraid-operation-lock.sh"' in content
    assert "acquire_little_orbit_operations_lock nonblocking" in dispatcher
    assert dispatcher.count('"outcome":"already_running"') == 1
    assert "acquire_little_orbit_operations_lock wait 300" in backup
    assert "acquire_little_orbit_operations_lock wait 300" in restore
    assert 'source "${SCRIPT_DIR}/unraid-operation-lock.sh"' in rotation
    assert "acquire_little_orbit_operations_lock wait 300" in rotation
    for content in (startup, bootstrap, firewall, installer):
        assert "unraid-operation-lock.sh" in content
        assert "acquire_little_orbit_operations_lock wait 300" in content
    assert "acquire_or_authorize_little_orbit_operations_lock wait 300" in stack


def test_migration_capability_is_tied_to_the_live_lock_inode() -> None:
    """A token alone cannot bypass a dead or replaced operations lock holder."""

    helper = script("unraid-operation-lock.sh")
    assert "regular file:0:0:600:1" in helper
    assert 'holder_inode="$(stat -Lc' in helper
    assert 'path_inode="$(stat -Lc' in helper
    assert '[[ "${holder_inode}" == "${path_inode}"' in helper
    assert "kill -0" in helper
    assert "flock --nonblock 8" in helper
    assert "unset LITTLE_ORBIT_MIGRATION_LOCK_TOKEN" in helper
    assert 'exec 9<>"${LITTLE_ORBIT_OPERATIONS_LOCK_PATH}"' in helper
    assert "LITTLE_ORBIT_MIGRATION_GUARD_PATH" in helper
    assert "flock --shared --wait" in helper
    assert "flock --exclusive --nonblock 9" in helper
    assert "run_little_orbit_migration_command" in helper
    assert "run_little_orbit_exclusive_command" in helper
    assert "export DOCKER_HOST=unix:///var/run/docker.sock" in helper


def test_migration_heartbeat_accepts_windows_crlf() -> None:
    """The Windows controller's text pipe cannot invalidate a live SSH lock."""

    helper = script("unraid-operation-lock.sh")
    assert "value=\"${value%$'\\r'}\"" in helper
    assert '[[ "${value}" == ping ]]' in helper


def test_background_mutation_services_have_real_health_checks() -> None:
    """Backup restart readiness never accepts a merely running worker."""

    compose = COMPOSE_PATH.read_text(encoding="utf-8")
    worker = compose.split("  worker:", maxsplit=1)[1].split(
        "\n  context-fetcher:", maxsplit=1
    )[0]
    media = compose.split("  media-worker:", maxsplit=1)[1].split(
        "\n  clamav:", maxsplit=1
    )[0]
    assert "healthcheck:" in worker
    assert "little_orbit_api.worker" in worker
    assert "('postgres', 5432)" in worker
    assert "healthcheck:" in media
    assert "little_orbit_api.attachment_media" in media
    assert "('postgres', 5432)" in media
    assert "('clamav', 3310)" in media


def test_internal_web_hop_avoids_the_existing_host_port_guard() -> None:
    """The private web flow must not collide with Scriptarr's port-3000 rule."""

    compose = COMPOSE_PATH.read_text(encoding="utf-8")
    caddy = (COMPOSE_PATH.parent / "gateway" / "Caddyfile").read_text(
        encoding="utf-8"
    )
    web = compose.split("  web:", maxsplit=1)[1].split("\n  api:", maxsplit=1)[0]
    assert 'PORT: "3014"' in web
    assert '"http://127.0.0.1:3014/status"' in web
    assert "reverse_proxy web:3014" in caddy
    assert "reverse_proxy web:3000" not in caddy


def test_ollama_receives_the_same_stable_gpu_lock_mount() -> None:
    """The GPU daemon can diagnose the inode held by its worker controller."""

    compose = COMPOSE_PATH.read_text(encoding="utf-8")
    unraid = (COMPOSE_PATH.parent / "compose.unraid.yaml").read_text(encoding="utf-8")
    ollama = compose.split("  ollama:", maxsplit=1)[1].split(
        "\n  model-init:", maxsplit=1
    )[0]
    unraid_ollama = unraid.split("  ollama:", maxsplit=1)[1].split(
        "\nnetworks:", maxsplit=1
    )[0]
    assert "gpu-coordinator:/run/gpu-coordinator" in ollama
    assert '"${GPU_COORDINATOR_GID:-2000}"' in ollama
    assert "${GPU_LOCK_HOST_PATH:?set GPU_LOCK_HOST_PATH}" in unraid_ollama
    assert "target: /run/gpu-coordinator/gpu.lock" in unraid_ollama


def test_user_scripts_require_explicit_post_cutover_activation() -> None:
    """Installation writes disabled metadata; only one named command enables jobs."""

    installer = script("unraid-install-user-scripts.sh")
    assert 'local mode="${1:-install}"' in installer
    assert "activate-after-cutover)" in installer
    assert 'startup_frequency="disabled"' in installer
    assert 'custom_frequency="disabled"' in installer
    assert '[[ "${mode}" == "activate-after-cutover" ]]' in installer
    assert 'write_schedules "${mode}"' in installer
    assert 'outcome="installed-inactive"' in installer
