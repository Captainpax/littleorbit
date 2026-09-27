from __future__ import annotations

from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]
RUNNER = REPO_ROOT / "infra" / "scripts" / "operations-runner.ps1"
BINARY_PIPELINE = REPO_ROOT / "infra" / "scripts" / "lib" / "Invoke-BinaryPipeline.ps1"
RESTORE_DRILL = REPO_ROOT / "infra" / "scripts" / "test-restore-latest.ps1"


def test_database_sql_is_streamed_without_native_argument_requoting() -> None:
    source = RUNNER.read_text(encoding="utf-8")

    assert "$output = $Sql | & $docker @composeArguments exec -T postgres psql" in source
    assert "--set=ON_ERROR_STOP=1 --file=-" in source
    assert "--command=$Sql" not in source


def test_database_sql_suppresses_psql_command_tags() -> None:
    """An empty UPDATE cannot be mistaken for a pending job claim."""

    source = RUNNER.read_text(encoding="utf-8")

    assert "--dbname=$databaseName --quiet --no-align --tuples-only" in source


def test_compose_binary_streams_drop_the_windows_utf8_bom() -> None:
    helper = BINARY_PIPELINE.read_text(encoding="utf-8")

    assert "[Console]::InputEncoding = [Text.UTF8Encoding]::new($false)" in helper
    assert "$destinationInput = $destination.StandardInput" in helper
    assert "$source.StandardOutput.BaseStream.CopyTo($destinationInput.BaseStream)" in helper
    assert "[Console]::InputEncoding = $originalInputEncoding" in helper


def test_restore_drill_arms_cleanup_before_restore_can_fail() -> None:
    source = RESTORE_DRILL.read_text(encoding="utf-8")

    cleanup_assignment = source.index("$cleanupDatabase = $true")
    restore_invocation = source.index('"restore-postgres.ps1"')
    assert cleanup_assignment < restore_invocation
    assert "if ($cleanupDatabase)" in source
    assert "dropdb" in source
    assert "--force --if-exists $databaseName" in source
