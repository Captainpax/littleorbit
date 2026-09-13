param(
    [Parameter(Mandatory = $true)][string]$BackupPath,
    [string]$ComposeFile = "infra/compose.yaml",
    [switch]$ConfirmDestructive
)

$ErrorActionPreference = "Stop"
if (-not $ConfirmDestructive) {
    throw "Attachment restore replaces current attachment bytes. Pass -ConfirmDestructive."
}
$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "../..")).Path
$resolvedBackup = (Resolve-Path -LiteralPath $BackupPath).Path
$repoPrefix = $repoRoot.TrimEnd([IO.Path]::DirectorySeparatorChar) + [IO.Path]::DirectorySeparatorChar
if ($resolvedBackup -ne $repoRoot -and
        -not $resolvedBackup.StartsWith($repoPrefix, [StringComparison]::OrdinalIgnoreCase)) {
    throw "Restore directory must be inside the Little Orbit workspace."
}
$payloadPath = Join-Path $resolvedBackup "payload"
$manifestPath = Join-Path $resolvedBackup "manifest.json"
if (-not (Test-Path -LiteralPath $payloadPath -PathType Container) -or
        -not (Test-Path -LiteralPath $manifestPath -PathType Leaf)) {
    throw "Attachment backup is incomplete."
}
$manifest = @(Get-Content -LiteralPath $manifestPath -Raw | ConvertFrom-Json)
$payloadPrefix = $payloadPath.TrimEnd([IO.Path]::DirectorySeparatorChar) + [IO.Path]::DirectorySeparatorChar
foreach ($entry in $manifest) {
    $candidate = [IO.Path]::GetFullPath((Join-Path $payloadPath $entry.path))
    if (-not $candidate.StartsWith($payloadPrefix, [StringComparison]::OrdinalIgnoreCase)) {
        throw "Attachment manifest contains an unsafe path."
    }
    if ((Get-Item -LiteralPath $candidate).Length -ne $entry.bytes -or
            (Get-FileHash -LiteralPath $candidate -Algorithm SHA256).Hash.ToLowerInvariant() -ne $entry.sha256) {
        throw "Attachment backup integrity check failed."
    }
}

Push-Location $repoRoot
try {
    $containerId = (docker compose --env-file .env -f $ComposeFile ps -q api).Trim()
    if (-not $containerId) {
        throw "API container is not running."
    }
    docker compose --env-file .env -f $ComposeFile stop gateway worker media-worker
    docker compose --env-file .env -f $ComposeFile exec -T api sh -c `
        'find /var/lib/little-orbit/attachments -mindepth 1 -delete'
    if ($LASTEXITCODE -ne 0) {
        throw "Could not clear the attachment volume."
    }
    docker compose --env-file .env -f $ComposeFile cp `
        "$payloadPath/." "api:/var/lib/little-orbit/attachments/"
    if ($LASTEXITCODE -ne 0) {
        throw "Attachment restore copy failed."
    }
}
finally {
    docker compose --env-file .env -f $ComposeFile start worker media-worker gateway
    Pop-Location
}
