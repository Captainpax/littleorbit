"""Local promotion, archive extraction, and shell syntax migration tests."""

from __future__ import annotations

import io
from pathlib import Path
import shutil
import subprocess
import tarfile

import pytest

from infra.scripts.tests.direct_migration_test_support import (
    MODULE,
    RESTORE,
    SCRIPT_DIR,
    arguments,
)


def test_local_pair_promotion_rolls_back_first_rename_on_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    value = arguments(tmp_path, "rollback")
    attachments = value.rollback_data_root / ".attachments-migration-test"
    releases = value.rollback_data_root / ".releases-migration-test"
    attachments.mkdir()
    releases.mkdir()
    (attachments / "one").write_bytes(b"one")
    real_replace = MODULE.artifacts.os.replace

    def replace(source: Path, destination: Path) -> None:
        if Path(destination).name == "releases":
            raise OSError("injected failure")
        real_replace(source, destination)

    monkeypatch.setattr(MODULE.artifacts.os, "replace", replace)
    with pytest.raises(OSError, match="injected"):
        MODULE.promote_local(value, attachments, releases)
    assert attachments.is_dir()
    assert not (value.rollback_data_root / "attachments").exists()


def test_rollback_cleanup_refuses_unexpected_paths(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    value = arguments(tmp_path, "rollback")
    unexpected = value.rollback_data_root / "operator-note.txt"
    unexpected.write_text("preserve", encoding="utf-8")
    monkeypatch.setattr(MODULE, "run_stack", lambda *_args, **_kwargs: "")
    with pytest.raises(RuntimeError, match="unexpected path"):
        MODULE.clean_rollback_destination(value)
    assert unexpected.read_text(encoding="utf-8") == "preserve"


def test_stage_restore_populates_only_disposable_root(tmp_path: Path) -> None:
    root = tmp_path / "sibling-stage"
    staging = root / ".restore-new-fixture"
    (staging / "nested").mkdir(parents=True)
    (staging / "nested" / "file").write_bytes(b"bytes")
    RESTORE.populate_empty_staging(staging, root)
    assert (root / "nested" / "file").read_bytes() == b"bytes"
    assert not staging.exists()


def test_release_extractor_rejects_links(tmp_path: Path) -> None:
    stream = io.BytesIO()
    with tarfile.open(fileobj=stream, mode="w") as archive:
        member = tarfile.TarInfo("unsafe-link")
        member.type = tarfile.SYMTYPE
        member.linkname = "elsewhere"
        archive.addfile(member)
    stream.seek(0)
    with pytest.raises(RuntimeError, match="non-regular"):
        MODULE.inventory.extract_release_archive(stream, tmp_path)


@pytest.mark.parametrize(
    "name",
    [r"C:\outside.txt", r"\\server\share\outside.txt", r"..\outside.txt", r"safe\nested.txt"],
)
def test_release_extractor_rejects_windows_path_forms(tmp_path: Path, name: str) -> None:
    stream = io.BytesIO()
    with tarfile.open(fileobj=stream, mode="w") as archive:
        member = tarfile.TarInfo(name)
        member.size = 1
        archive.addfile(member, io.BytesIO(b"x"))
    stream.seek(0)
    with pytest.raises(RuntimeError, match="unsafe path"):
        MODULE.inventory.extract_release_archive(stream, tmp_path)
    assert list(tmp_path.iterdir()) == []


def test_recovery_compose_uses_explicit_bind_root_and_loopback_gateway() -> None:
    override = (SCRIPT_DIR.parent / "compose.rollback.yaml").read_text(encoding="utf-8")
    assert all(value in override for value in ("${ROLLBACK_DATA_ROOT:?set ROLLBACK_DATA_ROOT}/attachments", "${ROLLBACK_DATA_ROOT:?set ROLLBACK_DATA_ROOT}/releases", "127.0.0.1"))


@pytest.mark.parametrize(
    "name",
    [
        "unraid-stack.sh", "unraid-bootstrap.sh", "unraid-firewall.sh",
        "unraid-timezone.sh", "unraid-user-script.sh", "unraid-backup.sh",
        "unraid-restore-drill.sh", "unraid-operations.sh", "unraid-install-user-scripts.sh",
    ],
)
def test_unraid_shell_entrypoints_parse(name: str) -> None:
    git_bash = Path("C:/Program Files/Git/bin/bash.exe")
    executable = str(git_bash) if git_bash.is_file() else shutil.which("bash")
    if executable is None:
        pytest.skip("Bash is unavailable")
    subprocess.run([executable, "-n", str(SCRIPT_DIR / name)], check=True)
