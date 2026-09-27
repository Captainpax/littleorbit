"""Bootstrap and storage-boundary invariants for the fixed Unraid host."""

from __future__ import annotations

from pathlib import Path
import subprocess

import pytest

from infra.scripts.tests.unraid_test_support import (
    BASH,
    SCRIPT_DIR,
    run_bash,
    safe_share_config,
    script,
)


def legacy_share_config() -> str:
    """Return the one upgradeable pre-NFS Little Orbit share policy."""

    return safe_share_config().replace('shareExportNFS="-"\n', "").replace(
        'shareSecurityNFS="private"\n', ""
    )


def upgrade_share(
    bootstrap: Path, config: Path, temporary_root: Path,
) -> subprocess.CompletedProcess[str]:
    """Run the legacy upgrade followed by the full current validator."""

    return run_bash(
        'source "$1"; test_temp="$3"; '
        'mktemp() { command mktemp "${test_temp}/.upgrade.XXXXXX"; }; '
        'upgrade_legacy_non_nfs_share "$2" test only cache; '
        'validate_share_config "$2" test only cache',
        bootstrap.resolve().as_posix(),
        config.resolve().as_posix(),
        temporary_root.resolve().as_posix(),
    )


def prepare_sentinel(
    bootstrap: Path, backup_root: Path, metadata: str = "regular file:0:0:600:1",
) -> subprocess.CompletedProcess[str]:
    """Probe sentinel policy with deterministic Unix metadata on any test host."""

    return run_bash(
        'export LITTLE_ORBIT_BACKUP_ROOT="$2"; source "$1"; metadata="$3"; '
        "stat() { printf '%s\\n' \"${metadata}\"; }; "
        "prepare_backup_placement_sentinel",
        bootstrap.resolve().as_posix(),
        backup_root.resolve().as_posix(),
        metadata,
    )


def test_bootstrap_requires_exact_unraid_mounts() -> None:
    """Root-filesystem lookalike directories cannot receive live state."""

    content = script("unraid-bootstrap.sh")
    assert "mountpoint --quiet --" in content
    assert "--output TARGET,SOURCE,FSTYPE" in content
    assert "require_unraid_mount /mnt/cache device btrfs" in content
    assert "require_unraid_mount /mnt/user shfs fuse.shfs" in content
    assert 'require_fixed_root "${DATA_ROOT}" /mnt/cache/little-orbit-live' in content
    assert (
        'require_fixed_root "${BACKUP_ROOT}" /mnt/user/little-orbit-backups' in content
    )
    assert 'require_fixed_root "${GPU_ROOT}" /mnt/cache/gpu-coordinator' in content


def test_bootstrap_fences_every_share_export_and_placement() -> None:
    """Little Orbit shares are unique, local-only, and pinned to reviewed storage."""

    content = script("unraid-bootstrap.sh")
    assert 'require_share_setting "${target}" "${name}" shareExport "-"' in content
    assert 'require_share_setting "${target}" "${name}" shareExportNFS "-"' in content
    assert 'require_share_setting "${target}" "${name}" shareCachePool2 ""' in content
    assert '[[ -f "${target}" && ! -L "${target}" ]]' in content
    assert '[[ "${filename,,}" == "${name,,}.cfg" ]]' in content
    assert "reject_duplicate_share_settings" in content
    cache_only = (
        "little-orbit-live",
        "little-orbit-deploy",
        "little-orbit-secrets",
        "gpu-coordinator",
        "little-orbit-tools",
    )
    for name in cache_only:
        assert f"configure_share {name} only cache" in content
    assert 'configure_share little-orbit-backups no ""' in content
    assert "require_array_disk_mount" in content and "--mountpoint" in content
    assert 'readonly UNRAID_EMCMD="/usr/local/sbin/emcmd"' in content
    assert '"${UNRAID_EMCMD}" "$1"' in content
    main = content.rsplit("main() {", maxsplit=1)[1]
    assert main.index("audit_all_share_placements") < main.index("configure_shares")
    assert main.index("configure_shares") < main.index("create_layout")
    assert main.index("create_layout") < main.index("verify_all_share_placements")


@pytest.mark.skipif(BASH is None, reason="a functioning Bash is unavailable")
def test_share_runtime_apply_is_exact_and_precedes_layout() -> None:
    """Persisted share policy is applied to live shfs before any data write."""

    bootstrap = SCRIPT_DIR / "unraid-bootstrap.sh"
    rendered = run_bash(
        'source "$1"; render_share_apply_request "$2" "$3" "$4" "$5"',
        bootstrap.resolve().as_posix(),
        "little-orbit-backups",
        "no",
        "",
        "Little Orbit encrypted array backups",
    )
    expected = (
        "cmdEditShare=Apply&shareNameOrig=little-orbit-backups"
        "&shareName=little-orbit-backups"
        "&shareComment=Little+Orbit+encrypted+array+backups"
        "&shareFloor=0&shareUseCache=no&shareCachePool=&shareCachePool2="
        "&shareAllocator=highwater&shareSplitLevel=&shareInclude=&shareExclude="
        "&shareCOW=auto"
    )
    assert rendered.returncode == 0, rendered.stderr
    assert rendered.stdout == expected
    invoked = run_bash(
        'source "$1"; run_unraid_emcmd() { printf "<%s>" "$1"; }; '
        'apply_share_runtime "$2" "$3" "$4" "$5"',
        bootstrap.resolve().as_posix(),
        "little-orbit-backups",
        "no",
        "",
        "Little Orbit encrypted array backups",
    )
    assert invoked.returncode == 0, invoked.stderr
    assert invoked.stdout == f"<{expected}>"
    content = script("unraid-bootstrap.sh")
    configure = content[content.index("configure_share() {"):content.index(
        "upgrade_legacy_non_nfs_share() {"
    )]
    first_validation = configure.index("validate_share_config")
    runtime_apply = configure.index("apply_share_runtime")
    assert first_validation < runtime_apply
    assert configure.index("validate_share_config", runtime_apply) > runtime_apply


@pytest.mark.skipif(BASH is None, reason="a functioning Bash is unavailable")
def test_cache_share_runtime_apply_keeps_the_fixed_pool() -> None:
    """The live refresh cannot drop the direct-cache primary storage setting."""

    rendered = run_bash(
        'source "$1"; render_share_apply_request "$2" "$3" "$4" "$5"',
        (SCRIPT_DIR / "unraid-bootstrap.sh").resolve().as_posix(),
        "little-orbit-live",
        "only",
        "cache",
        "Little Orbit direct-pool live state",
    )
    expected = (
        "cmdEditShare=Apply&shareNameOrig=little-orbit-live"
        "&shareName=little-orbit-live"
        "&shareComment=Little+Orbit+direct-pool+live+state"
        "&shareFloor=0&shareUseCache=only&shareCachePool=cache&shareCachePool2="
        "&shareAllocator=highwater&shareSplitLevel=&shareInclude=&shareExclude="
        "&shareCOW=auto"
    )
    assert rendered.returncode == 0, rendered.stderr
    assert rendered.stdout == expected


@pytest.mark.skipif(BASH is None, reason="a functioning Bash is unavailable")
def test_share_runtime_apply_propagates_management_failure() -> None:
    """A failed live policy refresh prevents bootstrap from reaching layout writes."""

    result = run_bash(
        'source "$1"; run_unraid_emcmd() { return 73; }; '
        'apply_share_runtime little-orbit-backups no "" "Little Orbit backups"',
        (SCRIPT_DIR / "unraid-bootstrap.sh").resolve().as_posix(),
    )
    assert result.returncode == 73


@pytest.mark.skipif(BASH is None, reason="a functioning Bash is unavailable")
def test_share_runtime_apply_rejects_unreviewed_values() -> None:
    """The management request cannot accept arbitrary names, pools, or text."""

    bootstrap = (SCRIPT_DIR / "unraid-bootstrap.sh").resolve().as_posix()
    probes = (
        ("../share", "no", "", "Little Orbit"),
        ("little-orbit-live", "prefer", "cache", "Little Orbit"),
        ("little-orbit-live", "only", "other", "Little Orbit"),
        ("little-orbit-live", "only", "cache", "Little Orbit&unsafe=true"),
    )
    for values in probes:
        result = run_bash(
            'source "$1"; render_share_apply_request "$2" "$3" "$4" "$5"',
            bootstrap,
            *values,
        )
        assert result.returncode == 64


@pytest.mark.skipif(BASH is None, reason="a functioning Bash is unavailable")
def test_share_validation_rejects_unsafe_settings_and_duplicates(
    tmp_path: Path,
) -> None:
    """A matching safe line cannot hide exports or a conflicting placement."""

    bootstrap = SCRIPT_DIR / "unraid-bootstrap.sh"
    config = tmp_path / "little-orbit-live.cfg"
    config_path = f"{tmp_path.resolve().as_posix()}/little-orbit-live.cfg"
    safe_config = safe_share_config()

    def validate() -> subprocess.CompletedProcess[str]:
        return run_bash(
            'source "$1"; validate_share_config "$2" test only cache',
            bootstrap.resolve().as_posix(),
            config_path,
        )

    config.write_text(safe_config, encoding="utf-8")
    assert validate().returncode == 0

    config.write_bytes(safe_config.replace("\n", "\r\n").encode())
    assert validate().returncode == 0

    config.write_text(
        safe_config.replace('shareExportNFS="-"', 'shareExportNFS="e"'),
        encoding="utf-8",
    )
    assert validate().returncode == 78

    unsafe_settings = (
        ('shareExport="-"', 'shareExport="e"'),
        ('shareUseCache="only"', 'shareUseCache="yes"'),
        ('shareCachePool="cache"', 'shareCachePool="other"'),
        ('shareCachePool2=""', 'shareCachePool2="other"'),
    )
    for safe, unsafe in unsafe_settings:
        config.write_text(safe_config.replace(safe, unsafe), encoding="utf-8")
        assert validate().returncode == 78

    config.write_text(safe_config + 'shareExport="-"\n', encoding="utf-8")
    duplicate = validate()
    assert duplicate.returncode == 78
    assert "Duplicate settings" in duplicate.stderr


@pytest.mark.skipif(BASH is None, reason="a functioning Bash is unavailable")
def test_legacy_share_upgrade_requires_both_nfs_keys_to_be_absent(
    tmp_path: Path,
) -> None:
    """Only the exact pre-NFS policy receives the two missing safe defaults."""

    bootstrap = SCRIPT_DIR / "unraid-bootstrap.sh"
    config = tmp_path / "little-orbit-live.cfg"
    legacy = legacy_share_config()
    config.write_text(legacy, encoding="utf-8")

    upgraded = upgrade_share(bootstrap, config, tmp_path)

    assert upgraded.returncode == 0, upgraded.stderr
    assert config.read_text(encoding="utf-8") == (
        legacy + 'shareExportNFS="-"\nshareSecurityNFS="private"\n'
    )


@pytest.mark.skipif(BASH is None, reason="a functioning Bash is unavailable")
@pytest.mark.parametrize(
    "unsafe",
    (
        legacy_share_config() + 'shareExportNFS="-"\n',
        legacy_share_config().replace('shareExport="-"', 'shareExport="e"'),
        safe_share_config().replace('shareSecurityNFS="private"', 'shareSecurityNFS="public"'),
    ),
)
def test_legacy_share_upgrade_rejects_partial_or_unsafe_policy(
    tmp_path: Path, unsafe: str,
) -> None:
    """Partial NFS policy and any wrong core value remain fail-closed."""

    config = tmp_path / "little-orbit-live.cfg"
    config.write_text(unsafe, encoding="utf-8")
    result = upgrade_share(SCRIPT_DIR / "unraid-bootstrap.sh", config, tmp_path)
    assert result.returncode == 78


@pytest.mark.skipif(BASH is None, reason="a functioning Bash is unavailable")
def test_legacy_share_upgrade_rejects_a_symlink(tmp_path: Path) -> None:
    """A legacy config cannot redirect the in-place upgrade."""

    target = tmp_path / "share-target.cfg"
    target.write_text(legacy_share_config(), encoding="utf-8")
    config = tmp_path / "little-orbit-live.cfg"
    try:
        config.symlink_to(target)
    except OSError:
        pytest.skip("the test host cannot create symbolic links")
    result = upgrade_share(SCRIPT_DIR / "unraid-bootstrap.sh", config, tmp_path)
    assert result.returncode == 78


@pytest.mark.skipif(BASH is None, reason="a functioning Bash is unavailable")
def test_backup_placement_sentinel_is_stable_and_proves_array_presence(
    tmp_path: Path,
) -> None:
    """The sentinel is idempotent and makes the reviewed array share observable."""

    bootstrap = SCRIPT_DIR / "unraid-bootstrap.sh"
    mount_root = tmp_path / "mnt"
    backup_root = mount_root / "disk1" / "little-orbit-backups"
    backup_root.mkdir(parents=True)
    first = prepare_sentinel(bootstrap, backup_root)
    sentinel = backup_root / ".array-placement"
    identity = (sentinel.stat().st_ino, sentinel.stat().st_mtime_ns)
    second = prepare_sentinel(bootstrap, backup_root)
    verified = run_bash(
        'source "$1"; verify_share_placement little-orbit-backups array "$2" false',
        bootstrap.resolve().as_posix(),
        mount_root.resolve().as_posix(),
    )
    assert first.returncode == second.returncode == verified.returncode == 0
    assert sentinel.read_bytes() == b"little-orbit-array-only\n"
    assert (sentinel.stat().st_ino, sentinel.stat().st_mtime_ns) == identity


@pytest.mark.skipif(BASH is None, reason="a functioning Bash is unavailable")
def test_backup_placement_sentinel_rejects_bad_metadata_and_content(
    tmp_path: Path,
) -> None:
    """An existing sentinel is accepted only with exact metadata and bytes."""

    bootstrap = SCRIPT_DIR / "unraid-bootstrap.sh"
    backup_root = tmp_path / "little-orbit-backups"
    backup_root.mkdir()
    sentinel = backup_root / ".array-placement"
    sentinel.write_text("little-orbit-array-only\n", encoding="utf-8")
    metadata = prepare_sentinel(bootstrap, backup_root, "regular file:0:0:644:1")
    sentinel.write_text("wrong-placement\n", encoding="utf-8")
    content = prepare_sentinel(bootstrap, backup_root)
    assert metadata.returncode == 78
    assert content.returncode == 78


@pytest.mark.skipif(BASH is None, reason="a functioning Bash is unavailable")
def test_share_validation_rejects_symlinks_and_ambiguous_names(tmp_path: Path) -> None:
    """Share policy cannot be redirected or shadowed by a case-variant file."""

    bootstrap = SCRIPT_DIR / "unraid-bootstrap.sh"
    config = tmp_path / "little-orbit-live.cfg"
    config_path = f"{tmp_path.resolve().as_posix()}/little-orbit-live.cfg"
    safe_config = safe_share_config()
    symlink_target = tmp_path / "safe-share.cfg"
    symlink_target.write_text(safe_config, encoding="utf-8")
    validate_command = 'source "$1"; validate_share_config "$2" test only cache'
    try:
        config.symlink_to(symlink_target)
    except OSError:
        pass
    else:
        result = run_bash(validate_command, bootstrap.resolve().as_posix(), config_path)
        assert result.returncode == 78
        config.unlink()

    ambiguous = tmp_path / "Little-Orbit-Live.cfg"
    ambiguous.write_text(safe_config, encoding="utf-8")
    result = run_bash(
        'source "$1"; require_unambiguous_share_config "$2" "$3" "$4"',
        bootstrap.resolve().as_posix(),
        "little-orbit-live",
        config_path,
        tmp_path.resolve().as_posix(),
    )
    assert result.returncode == 78
    assert "Ambiguous share configuration name" in result.stderr


@pytest.mark.skipif(BASH is None, reason="a functioning Bash is unavailable")
def test_share_placement_rejects_every_wrong_storage_tier(tmp_path: Path) -> None:
    """Config policy cannot hide stale data on the array, cache, or another pool."""

    bootstrap = SCRIPT_DIR / "unraid-bootstrap.sh"
    mount_root = tmp_path / "mnt"
    for storage in ("cache", "disk1", "user", "other-pool"):
        (mount_root / storage).mkdir(parents=True)
    (mount_root / "cache" / "little-orbit-live").mkdir()
    (mount_root / "disk1" / "little-orbit-backups").mkdir()

    def audit(name: str, policy: str) -> subprocess.CompletedProcess[str]:
        return run_bash(
            'source "$1"; audit_share_placement "$2" "$3" "$4" false',
            bootstrap.resolve().as_posix(),
            name,
            policy,
            mount_root.resolve().as_posix(),
        )

    assert audit("little-orbit-live", "cache").returncode == 0
    assert audit("little-orbit-backups", "array").returncode == 0
    verify = 'source "$1"; verify_share_placement "$2" "$3" "$4" false'
    for name, policy in (
        ("little-orbit-live", "cache"),
        ("little-orbit-backups", "array"),
    ):
        result = run_bash(
            verify, bootstrap.resolve().as_posix(), name, policy, mount_root.as_posix()
        )
        assert result.returncode == 0

    wrong_case = mount_root / "disk1" / "Little-Orbit-Live"
    wrong_case.mkdir()
    assert audit("little-orbit-live", "cache").returncode == 78
    wrong_case.rmdir()
    (mount_root / "disk1" / "little-orbit-live").mkdir()
    assert audit("little-orbit-live", "cache").returncode == 78
    (mount_root / "cache" / "little-orbit-backups").mkdir()
    assert audit("little-orbit-backups", "array").returncode == 78
    (mount_root / "other-pool" / "little-orbit-tools").mkdir()
    assert audit("little-orbit-tools", "cache").returncode == 78
