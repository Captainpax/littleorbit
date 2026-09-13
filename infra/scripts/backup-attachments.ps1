param(
    [string]$ComposeFile = "infra/compose.yaml",
    [string]$Destination = "backups/attachments",
    [int]$RetentionDays = 14
)

$ErrorActionPreference = "Stop"
$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "../..")).Path
$destinationPath = [IO.Path]::GetFullPath((Join-Path $repoRoot $Destination))
$repoPrefix = $repoRoot.TrimEnd([IO.Path]::DirectorySeparatorChar) + [IO.Path]::DirectorySeparatorChar
if ($destinationPath -ne $repoRoot -and
        -not $destinationPath.StartsWith($repoPrefix, [StringComparison]::OrdinalIgnoreCase)) {
    throw "Backup destination must stay inside the Little Orbit workspace."
}
New-Item -ItemType Directory -Force -Path $destinationPath | Out-Null
$timestamp = Get-Date -Format "yyyyMMdd-HHmmss"
$partialPath = Join-Path $destinationPath ".little-orbit-attachments-$timestamp.partial"
$outputPath = Join-Path $destinationPath "little-orbit-attachments-$timestamp.files"
$payloadPath = Join-Path $partialPath "payload"
New-Item -ItemType Directory -Force -Path $payloadPath | Out-Null

Push-Location $repoRoot
try {
    $containerId = (docker compose --env-file .env -f $ComposeFile ps -q api).Trim()
    if (-not $containerId) {
        throw "API container is not running."
    }
    docker compose --env-file .env -f $ComposeFile cp `
        "api:/var/lib/little-orbit/attachments/." $payloadPath
    if ($LASTEXITCODE -ne 0) {
        throw "Attachment volume copy failed."
    }
    $entries = @(Get-ChildItem -LiteralPath $payloadPath -File -Recurse | ForEach-Object {
        [PSCustomObject]@{
            path = [IO.Path]::GetRelativePath($payloadPath, $_.FullName).Replace("\", "/")
            bytes = $_.Length
            sha256 = (Get-FileHash -LiteralPath $_.FullName -Algorithm SHA256).Hash.ToLowerInvariant()
        }
    })
    ConvertTo-Json -InputObject $entries -Depth 3 | Set-Content `
        -LiteralPath (Join-Path $partialPath "manifest.json") -Encoding utf8
    Move-Item -LiteralPath $partialPath -Destination $outputPath
    Get-ChildItem -LiteralPath $destinationPath -Directory `
        -Filter "little-orbit-attachments-*.files" |
        Where-Object LastWriteTime -LT (Get-Date).AddDays(-$RetentionDays) |
        ForEach-Object {
            if (-not $_.FullName.StartsWith($destinationPath, [StringComparison]::OrdinalIgnoreCase)) {
                throw "Retention target escaped the attachment backup directory."
            }
            Remove-Item -LiteralPath $_.FullName -Recurse -Force
        }
    Write-Output $outputPath
}
finally {
    if (Test-Path -LiteralPath $partialPath) {
        Remove-Item -LiteralPath $partialPath -Recurse -Force
    }
    Pop-Location
}
