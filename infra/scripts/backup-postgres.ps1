param(
    [string]$ComposeFile = "infra/compose.yaml",
    [string]$Destination = "backups/postgres",
    [int]$RetentionDays = 14
)

$ErrorActionPreference = "Stop"
$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "../..")).Path
$destinationPath = Join-Path $repoRoot $Destination
New-Item -ItemType Directory -Force -Path $destinationPath | Out-Null
$timestamp = Get-Date -Format "yyyyMMdd-HHmmss"
$outputPath = Join-Path $destinationPath "little-orbit-$timestamp.dump"

Push-Location $repoRoot
try {
    $containerDump = "/tmp/little-orbit-backup.dump"
    $containerId = (docker compose --env-file .env -f $ComposeFile ps -q postgres).Trim()
    if (-not $containerId) {
        throw "PostgreSQL container is not running."
    }
    docker compose --env-file .env -f $ComposeFile exec -T postgres sh -c 'pg_dump --format=custom --username="$POSTGRES_USER" --file=/tmp/little-orbit-backup.dump "$POSTGRES_DB"'
    if ($LASTEXITCODE -ne 0) {
        throw "pg_dump failed."
    }
    docker cp "${containerId}:${containerDump}" $outputPath
    docker compose --env-file .env -f $ComposeFile exec -T postgres rm -f $containerDump
    if ((Get-Item -LiteralPath $outputPath).Length -lt 1024) {
        throw "Backup output is unexpectedly small."
    }
    Get-ChildItem -LiteralPath $destinationPath -Filter "little-orbit-*.dump" |
        Where-Object LastWriteTime -LT (Get-Date).AddDays(-$RetentionDays) |
        Remove-Item -Force
    Write-Output $outputPath
}
finally {
    if ($containerId) {
        docker compose --env-file .env -f $ComposeFile exec -T postgres rm -f /tmp/little-orbit-backup.dump 2>$null
    }
    Pop-Location
}
