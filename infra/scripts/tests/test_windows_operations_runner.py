from __future__ import annotations

import json
import os
from pathlib import Path
import shutil
import subprocess

import pytest


REPO_ROOT = Path(__file__).resolve().parents[3]
RUNNER = REPO_ROOT / "infra" / "scripts" / "operations-runner.ps1"
BINARY_PIPELINE = REPO_ROOT / "infra" / "scripts" / "lib" / "Invoke-BinaryPipeline.ps1"
RESTORE_DRILL = REPO_ROOT / "infra" / "scripts" / "test-restore-latest.ps1"
PWSH = shutil.which("pwsh")


def _parse_pending_claim(lines: list[str] | None) -> subprocess.CompletedProcess[str]:
    if PWSH is None:
        raise RuntimeError("PowerShell is unavailable")
    environment = os.environ.copy()
    environment["LITTLE_ORBIT_RUNNER_PATH"] = str(RUNNER)
    environment["LITTLE_ORBIT_CLAIM_JSON"] = json.dumps(
        {"has_output": lines is not None, "lines": lines or []}
    )
    return subprocess.run(
        [
            PWSH,
            "-NoLogo",
            "-NoProfile",
            "-NonInteractive",
            "-Command",
            r"""
$tokens = $null
$parseErrors = $null
$ast = [Management.Automation.Language.Parser]::ParseFile(
    $env:LITTLE_ORBIT_RUNNER_PATH,
    [ref]$tokens,
    [ref]$parseErrors
)
if ($parseErrors.Count -ne 0) {
    [Console]::Error.WriteLine("Runner source did not parse.")
    exit 70
}
$definition = $ast.Find({
    param($node)
    $node -is [Management.Automation.Language.FunctionDefinitionAst] -and
        $node.Name -eq "ConvertFrom-PendingJobClaim"
}, $true)
Invoke-Expression $definition.Extent.Text
$payload = ConvertFrom-Json $env:LITTLE_ORBIT_CLAIM_JSON
$claimOutput = if ($payload.has_output) { @($payload.lines) } else { $null }
try {
    $claim = ConvertFrom-PendingJobClaim -ClaimOutput $claimOutput
    if ($null -eq $claim) {
        [Console]::Out.Write("null")
    }
    else {
        [Console]::Out.Write(($claim | ConvertTo-Json -Compress))
    }
}
catch {
    [Console]::Error.WriteLine($_.Exception.Message)
    exit 65
}
""",
        ],
        check=False,
        capture_output=True,
        text=True,
        timeout=10,
        env=environment,
    )


def test_database_sql_is_streamed_without_native_argument_requoting() -> None:
    source = RUNNER.read_text(encoding="utf-8")

    assert "$output = $Sql | & $docker @composeArguments exec -T postgres psql" in source
    assert "--set=ON_ERROR_STOP=1 --file=-" in source
    assert "--command=$Sql" not in source


def test_database_sql_suppresses_psql_command_tags() -> None:
    """An empty UPDATE cannot be mistaken for a pending job claim."""

    source = RUNNER.read_text(encoding="utf-8")

    assert "--dbname=$databaseName --no-psqlrc --quiet --no-align --tuples-only" in source
    assert "foreach ($line in @($output))" in source
    assert 'return ("$output").Trim()' not in source


@pytest.mark.skipif(PWSH is None, reason="PowerShell is unavailable")
def test_pending_claim_parser_accepts_no_row_or_one_canonical_row() -> None:
    empty = _parse_pending_claim(None)
    valid = _parse_pending_claim(
        ["12345678-1234-1234-1234-123456789abc|test_restore"]
    )

    assert empty.returncode == 0
    assert empty.stdout == "null"
    assert empty.stderr == ""
    assert valid.returncode == 0
    assert json.loads(valid.stdout) == {
        "JobId": "12345678-1234-1234-1234-123456789abc",
        "Kind": "test_restore",
    }
    assert valid.stderr == ""


@pytest.mark.skipif(PWSH is None, reason="PowerShell is unavailable")
@pytest.mark.parametrize(
    "lines",
    [
        ["UPDATE 0"],
        ["12345678-1234-1234-1234-123456789abc|backup", "UPDATE 1"],
        [
            "12345678-1234-1234-1234-123456789abc|backup",
            "22345678-1234-1234-1234-123456789abc|backup",
        ],
        ["12345678-1234-1234-1234-123456789abc|backup|test_restore"],
        ["12345678-1234-1234-1234-123456789ABC|backup"],
        ["psql startup notice", "12345678-1234-1234-1234-123456789abc|backup"],
        ["12345678-1234-1234-1234-123456789abc|arbitrary_command"],
    ],
    ids=[
        "update-tag",
        "row-plus-update-tag",
        "extra-row",
        "extra-delimiter",
        "noncanonical-uuid",
        "startup-file-contamination",
        "non-allowlisted-kind",
    ],
)
def test_pending_claim_parser_rejects_contaminated_output(lines: list[str]) -> None:
    result = _parse_pending_claim(lines)

    assert result.returncode == 65
    assert result.stdout == ""
    assert result.stderr == "The claimed operations job was malformed.\n"


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
