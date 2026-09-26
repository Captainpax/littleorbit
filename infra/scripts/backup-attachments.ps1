param(
    [string]$ComposeFile = "infra/compose.yaml",
    [string]$Destination = "backups/attachments",
    [int]$RetentionDays = 14,
    [string]$AgeRecipient = $env:BACKUP_AGE_RECIPIENT,
    [switch]$ServicesAlreadyStopped
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"
. (Join-Path $PSScriptRoot "lib/Invoke-BinaryPipeline.ps1")

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "../..")).Path
$destinationPath = [IO.Path]::GetFullPath((Join-Path $repoRoot $Destination))
$repoPrefix = $repoRoot.TrimEnd([IO.Path]::DirectorySeparatorChar) + [IO.Path]::DirectorySeparatorChar
if (-not $destinationPath.StartsWith($repoPrefix, [StringComparison]::OrdinalIgnoreCase)) {
    throw "Backup destination must stay inside the Little Orbit workspace."
}
if (-not $AgeRecipient) {
    $recipientLine = Get-Content -LiteralPath (Join-Path $repoRoot ".env") |
        Where-Object { $_ -match '^BACKUP_AGE_RECIPIENT=' } | Select-Object -Last 1
    if ($recipientLine) {
        $AgeRecipient = $recipientLine.Substring($recipientLine.IndexOf('=') + 1).Trim()
    }
}
if ($AgeRecipient -notmatch '^age1[023456789acdefghjklmnpqrstuvwxyz]{58}$') {
    throw "Set BACKUP_AGE_RECIPIENT to a valid age recipient."
}

New-Item -ItemType Directory -Force -Path $destinationPath | Out-Null
$timestamp = Get-Date -Format "yyyyMMdd-HHmmss"
$partialPath = Join-Path $destinationPath ".little-orbit-attachments-$timestamp.tar.age.partial"
$outputPath = Join-Path $destinationPath "little-orbit-attachments-$timestamp.tar.age"
$metadataPath = "$outputPath.json"
$streamScript = Get-Content -LiteralPath (Join-Path $PSScriptRoot "stream-attachment-backup.py") -Raw
$docker = (Get-Command docker -ErrorAction Stop).Source
$age = (Get-Command age -ErrorAction Stop).Source
$composeArguments = @("compose", "--env-file", ".env", "-f", $ComposeFile)

Push-Location $repoRoot
$pausedServices = $false
$serviceIds = @()
try {
    if (-not $ServicesAlreadyStopped) {
        $containerId = (& $docker @composeArguments ps -q api).Trim()
        if (-not $containerId) {
            throw "API container is not running."
        }
        $serviceIds = @(& $docker @composeArguments ps -q api worker media-worker) |
            Where-Object { $_ }
        & $docker @composeArguments stop api worker media-worker
        if ($LASTEXITCODE -ne 0) {
            throw "Could not pause attachment mutation services."
        }
        $pausedServices = $true
    }
    Invoke-BinaryPipeline `
        -SourceFile $docker `
        -SourceArguments ($composeArguments + @(
            "run", "--rm", "-T", "--no-deps", "--entrypoint", "python",
            "attachment-init", "-c", $streamScript)) `
        -DestinationFile $age `
        -DestinationArguments @("--encrypt", "--recipient", $AgeRecipient, "--output", $partialPath)
    if ((Get-Item -LiteralPath $partialPath).Length -lt 512) {
        throw "Encrypted attachment backup output is unexpectedly small."
    }
    Move-Item -LiteralPath $partialPath -Destination $outputPath
    $metadata = [ordered]@{
        kind = "little-orbit-attachments"
        created_at = (Get-Date).ToUniversalTime().ToString("o")
        encrypted_file = [IO.Path]::GetFileName($outputPath)
        encrypted_bytes = (Get-Item -LiteralPath $outputPath).Length
        encrypted_sha256 = (Get-FileHash -LiteralPath $outputPath -Algorithm SHA256).Hash.ToLowerInvariant()
        mutation_services_paused = $true
    }
    $metadata | ConvertTo-Json | Set-Content -LiteralPath $metadataPath -Encoding utf8
    Get-ChildItem -LiteralPath $destinationPath -File -Filter "little-orbit-attachments-*.tar.age" |
        Where-Object LastWriteTime -LT (Get-Date).AddDays(-$RetentionDays) |
        ForEach-Object {
            Remove-Item -LiteralPath $_.FullName -Force
            Remove-Item -LiteralPath "$($_.FullName).json" -Force -ErrorAction SilentlyContinue
        }
    Write-Output $outputPath
}
finally {
    Remove-Item -LiteralPath $partialPath -Force -ErrorAction SilentlyContinue
    if ($pausedServices) {
        & $docker start @serviceIds | Out-Null
    }
    Pop-Location
}
