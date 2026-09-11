param(
    [Parameter(Mandatory = $true)][string]$BackupPath,
    [string]$ComposeFile = "infra/compose.yaml",
    [string]$TargetDatabase = ""
)

$ErrorActionPreference = "Stop"
$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "../..")).Path
$resolvedBackup = (Resolve-Path -LiteralPath $BackupPath).Path
if (-not $resolvedBackup.StartsWith($repoRoot, [StringComparison]::OrdinalIgnoreCase)) {
    throw "Restore file must be inside the Little Orbit workspace."
}
if ($TargetDatabase -and $TargetDatabase -notmatch '^[a-zA-Z][a-zA-Z0-9_]{0,62}$') {
    throw "Target database must be a simple PostgreSQL identifier."
}

Push-Location $repoRoot
try {
    $databaseName = $TargetDatabase
    if (-not $databaseName) {
        $databaseName = (docker compose --env-file .env -f $ComposeFile exec -T postgres printenv POSTGRES_DB).Trim()
    }
    $databaseUser = (docker compose --env-file .env -f $ComposeFile exec -T postgres printenv POSTGRES_USER).Trim()
    $containerId = (docker compose --env-file .env -f $ComposeFile ps -q postgres).Trim()
    if (-not $containerId) {
        throw "PostgreSQL container is not running."
    }
    $containerDump = "/tmp/little-orbit-restore.dump"
    docker cp $resolvedBackup "${containerId}:${containerDump}"
    docker compose --env-file .env -f $ComposeFile exec -T postgres pg_restore --clean --if-exists --no-owner --username=$databaseUser --dbname=$databaseName $containerDump
    if ($LASTEXITCODE -ne 0) {
        throw "pg_restore failed."
    }
}
finally {
    if ($containerId) {
        docker compose --env-file .env -f $ComposeFile exec -T postgres rm -f /tmp/little-orbit-restore.dump 2>$null
    }
    Pop-Location
}
