"""Focused coverage for repository quality-source discovery."""

from __future__ import annotations

from pathlib import Path

import pytest

from infra.scripts.tests.direct_migration_test_support import load_script

QUALITY = load_script("check_quality.py")


def test_quality_checker_configures_infra_python_only() -> None:
    root, suffixes = QUALITY.SOURCE_ROOTS[-1]
    assert root == QUALITY.ROOT / "infra" / "scripts"
    assert suffixes == {".py"}


def test_quality_checker_excludes_generated_fixture_and_venv_directories(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source_root = tmp_path / "scripts"
    source_root.mkdir()
    included = source_root / "migration.py"
    included.write_text("def migrate() -> None:\n    pass\n", encoding="utf-8")
    (source_root / "migration.ps1").write_text("exit 0\n", encoding="utf-8")
    for name in ("fixtures", "generated", "__pycache__", ".venv313", "venv"):
        directory = source_root / name
        directory.mkdir()
        (directory / "ignored.py").write_text("raise AssertionError\n", encoding="utf-8")
    monkeypatch.setattr(QUALITY, "SOURCE_ROOTS", ((source_root, {".py"}),))
    assert QUALITY._source_files() == [included]
