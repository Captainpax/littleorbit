param(
    [string]$ComposeFile = "infra/compose.yaml",
    [string]$PostgresDestination = "backups/postgres",
    [string]$AttachmentDestination = "backups/attachments",
    [int]$RetentionDays = 14,
    [string]$AgeRecipient = $env:BACKUP_AGE_RECIPIENT
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"
$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "../..")).Path
$docker = (Get-Command docker -ErrorAction Stop).Source
$composeArguments = @("compose", "--env-file", ".env", "-f", $ComposeFile)
$paused = $false
$serviceIds = @()

Push-Location $repoRoot
try {
    $containerId = (& $docker @composeArguments ps -q api).Trim()
    if (-not $containerId) {
        throw "API container is not running."
    }
    $serviceIds = @(& $docker @composeArguments ps -q api worker media-worker) |
        Where-Object { $_ }
    & $docker @composeArguments stop api worker media-worker
    if ($LASTEXITCODE -ne 0) {
        throw "Could not pause mutation services for the coordinated backup."
    }
    $paused = $true
    $database = & (Join-Path $PSScriptRoot "backup-postgres.ps1") `
        -ComposeFile $ComposeFile `
        -Destination $PostgresDestination `
        -RetentionDays $RetentionDays `
        -AgeRecipient $AgeRecipient
    $attachments = & (Join-Path $PSScriptRoot "backup-attachments.ps1") `
        -ComposeFile $ComposeFile `
        -Destination $AttachmentDestination `
        -RetentionDays $RetentionDays `
        -AgeRecipient $AgeRecipient `
        -ServicesAlreadyStopped
    [ordered]@{
        created_at = (Get-Date).ToUniversalTime().ToString("o")
        database = "$database".Trim()
        attachments = "$attachments".Trim()
        raw_coordinates_included = $false
    } | ConvertTo-Json
}
finally {
    if ($paused) {
        & $docker start @serviceIds | Out-Null
    }
    Pop-Location
}
