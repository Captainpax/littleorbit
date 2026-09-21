param(
    [string]$ComposeFile = "infra/compose.yaml",
    [string]$PostgresDestination = "backups/postgres",
    [string]$AttachmentDestination = "backups/attachments",
    [string]$PairManifestDestination = "backups/manifests",
    [int]$RetentionDays = 14,
    [string]$AgeRecipient = $env:BACKUP_AGE_RECIPIENT,
    [string]$OffHostDestination = $env:LITTLE_ORBIT_OFFHOST_BACKUP_DIR
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"
$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "../..")).Path
$repoPrefix = $repoRoot.TrimEnd([IO.Path]::DirectorySeparatorChar) + [IO.Path]::DirectorySeparatorChar
$pairDirectory = [IO.Path]::GetFullPath((Join-Path $repoRoot $PairManifestDestination))
if (-not $pairDirectory.StartsWith($repoPrefix, [StringComparison]::OrdinalIgnoreCase)) {
    throw "Pair-manifest destination must stay inside the Little Orbit workspace."
}
$docker = (Get-Command docker -ErrorAction Stop).Source
$composeArguments = @("compose", "--env-file", ".env", "-f", $ComposeFile)
$paused = $false
$serviceIds = @()
$pairPartial = $null

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
    $databasePath = "$database".Trim()
    $attachmentPath = "$attachments".Trim()
    New-Item -ItemType Directory -Force -Path $pairDirectory | Out-Null
    $pairTimestamp = (Get-Date).ToUniversalTime().ToString("yyyyMMdd-HHmmssfff")
    $pairPath = Join-Path $pairDirectory "little-orbit-pair-$pairTimestamp.json"
    $pairPartial = "$pairPath.partial"
    if (Test-Path -LiteralPath $pairPath) {
        throw "The coordinated backup pair manifest already exists."
    }
    $pair = [ordered]@{
        schema_version = 1
        created_at = (Get-Date).ToUniversalTime().ToString("o")
        database = [ordered]@{
            path = ([IO.Path]::GetRelativePath($repoRoot, $databasePath)).Replace('\', '/')
            bytes = (Get-Item -LiteralPath $databasePath).Length
            sha256 = (Get-FileHash -LiteralPath $databasePath -Algorithm SHA256).Hash.ToLowerInvariant()
        }
        attachments = [ordered]@{
            path = ([IO.Path]::GetRelativePath($repoRoot, $attachmentPath)).Replace('\', '/')
            bytes = (Get-Item -LiteralPath $attachmentPath).Length
            sha256 = (Get-FileHash -LiteralPath $attachmentPath -Algorithm SHA256).Hash.ToLowerInvariant()
        }
        raw_coordinates_included = $false
        attributable_quiz_feedback_included = $false
        anonymous_review_rows_included = $false
    }
    $pair | ConvertTo-Json -Depth 4 | Set-Content -LiteralPath $pairPartial -Encoding utf8
    Move-Item -LiteralPath $pairPartial -Destination $pairPath
    $offHostCopied = $false
    if ($OffHostDestination) {
        $offHostPath = [IO.Path]::GetFullPath($OffHostDestination)
        if ($offHostPath.StartsWith($repoPrefix, [StringComparison]::OrdinalIgnoreCase)) {
            throw "The off-host backup destination must be outside the Little Orbit workspace."
        }
        if ([IO.Path]::GetPathRoot($offHostPath) -eq $offHostPath) {
            throw "The off-host backup destination cannot be a filesystem root."
        }
        $copyName = Get-Date -Format "yyyyMMdd-HHmmss"
        $copyDirectory = Join-Path $offHostPath $copyName
        $partialDirectory = Join-Path $offHostPath (".$copyName.partial-" + [Guid]::NewGuid())
        $offHostPrefix = $offHostPath.TrimEnd([IO.Path]::DirectorySeparatorChar) + [IO.Path]::DirectorySeparatorChar
        if (
            -not $copyDirectory.StartsWith($offHostPrefix, [StringComparison]::OrdinalIgnoreCase) -or
            -not $partialDirectory.StartsWith($offHostPrefix, [StringComparison]::OrdinalIgnoreCase)
        ) {
            throw "The off-host copy path was rejected."
        }
        if (Test-Path -LiteralPath $copyDirectory) {
            throw "The off-host backup pair already exists."
        }
        New-Item -ItemType Directory -Path $partialDirectory -ErrorAction Stop | Out-Null
        foreach ($source in @(
            $databasePath,
            "$databasePath.json",
            $attachmentPath,
            "$attachmentPath.json",
            $pairPath
        )) {
            Copy-Item -LiteralPath $source -Destination $partialDirectory -ErrorAction Stop
            $copy = Join-Path $partialDirectory ([IO.Path]::GetFileName($source))
            $sourceHash = (Get-FileHash -LiteralPath $source -Algorithm SHA256).Hash
            $copyHash = (Get-FileHash -LiteralPath $copy -Algorithm SHA256).Hash
            if ($sourceHash -ne $copyHash) {
                throw "An off-host encrypted backup copy failed verification."
            }
        }
        Move-Item -LiteralPath $partialDirectory -Destination $copyDirectory
        $offHostCopied = $true
    }
    [ordered]@{
        created_at = (Get-Date).ToUniversalTime().ToString("o")
        database = $databasePath
        attachments = $attachmentPath
        pair_manifest = $pairPath
        off_host_copy = $offHostCopied
        raw_coordinates_included = $false
        attributable_quiz_feedback_included = $false
        anonymous_review_rows_included = $false
    } | ConvertTo-Json
}
finally {
    if ($pairPartial) {
        Remove-Item -LiteralPath $pairPartial -Force -ErrorAction SilentlyContinue
    }
    if ($paused) {
        & $docker start @serviceIds | Out-Null
    }
    Pop-Location
}
