param(
    [string]$ComposeFile = "infra/compose.yaml",
    [string]$PostgresBackupDirectory = "backups/postgres",
    [string]$AttachmentBackupDirectory = "backups/attachments",
    [string]$PairManifestDirectory = "backups/manifests",
    [string]$IdentityPath = (Join-Path $env:LOCALAPPDATA "LittleOrbit/backup-age-identity.txt")
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"
. (Join-Path $PSScriptRoot "lib/Invoke-BinaryPipeline.ps1")

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "../..")).Path
$databaseDirectory = [IO.Path]::GetFullPath((Join-Path $repoRoot $PostgresBackupDirectory))
$attachmentDirectory = [IO.Path]::GetFullPath((Join-Path $repoRoot $AttachmentBackupDirectory))
$pairDirectory = [IO.Path]::GetFullPath((Join-Path $repoRoot $PairManifestDirectory))
$repoPrefix = $repoRoot.TrimEnd([IO.Path]::DirectorySeparatorChar) + [IO.Path]::DirectorySeparatorChar
foreach ($directory in @($databaseDirectory, $attachmentDirectory, $pairDirectory)) {
    if (-not $directory.StartsWith($repoPrefix, [StringComparison]::OrdinalIgnoreCase)) {
        throw "Restore-drill backup directories must stay inside the Little Orbit workspace."
    }
}
if (-not (Test-Path -LiteralPath $IdentityPath -PathType Leaf)) {
    throw "The age identity file is unavailable."
}

$pairManifest = Get-ChildItem -LiteralPath $pairDirectory -File -Filter "little-orbit-pair-*.json" |
    Sort-Object LastWriteTimeUtc -Descending | Select-Object -First 1
if (-not $pairManifest) {
    throw "A coordinated backup pair manifest is required for a restore drill."
}
$pair = Get-Content -LiteralPath $pairManifest.FullName -Raw | ConvertFrom-Json
if (
    $pair.schema_version -ne 1 -or
    $pair.raw_coordinates_included -ne $false -or
    $pair.attributable_quiz_feedback_included -ne $false -or
    $pair.anonymous_review_rows_included -ne $false
) {
    throw "The coordinated backup pair manifest is invalid."
}

function Resolve-PairedBackup {
    param(
        [Parameter(Mandatory = $true)]$Entry,
        [Parameter(Mandatory = $true)][string]$ExpectedDirectory,
        [Parameter(Mandatory = $true)][string]$FilePattern
    )

    $candidate = [IO.Path]::GetFullPath((Join-Path $repoRoot ([string]$Entry.path)))
    $expectedPrefix = $ExpectedDirectory.TrimEnd([IO.Path]::DirectorySeparatorChar) + [IO.Path]::DirectorySeparatorChar
    if (-not $candidate.StartsWith($expectedPrefix, [StringComparison]::OrdinalIgnoreCase)) {
        throw "A paired backup path escaped its expected directory."
    }
    if ([IO.Path]::GetFileName($candidate) -notmatch $FilePattern) {
        throw "A paired backup filename was rejected."
    }
    $item = Get-Item -LiteralPath $candidate -ErrorAction Stop
    $digest = (Get-FileHash -LiteralPath $candidate -Algorithm SHA256).Hash.ToLowerInvariant()
    if ($item.Length -ne [long]$Entry.bytes -or $digest -ne [string]$Entry.sha256) {
        throw "A paired encrypted backup failed size or SHA-256 verification."
    }
    return $item
}

$databaseBackup = Resolve-PairedBackup `
    -Entry $pair.database `
    -ExpectedDirectory $databaseDirectory `
    -FilePattern '^little-orbit-[0-9]{8}-[0-9]{6}\.dump\.age$'
$attachmentBackup = Resolve-PairedBackup `
    -Entry $pair.attachments `
    -ExpectedDirectory $attachmentDirectory `
    -FilePattern '^little-orbit-attachments-[0-9]{8}-[0-9]{6}\.tar\.age$'

$databaseName = "little_orbit_drill_" + (Get-Date -Format "yyyyMMddHHmmss")
$docker = (Get-Command docker -ErrorAction Stop).Source
$age = (Get-Command age -ErrorAction Stop).Source
$composeArguments = @("compose", "--env-file", ".env", "-f", $ComposeFile)
$verifier = Get-Content -LiteralPath (Join-Path $PSScriptRoot "verify-attachment-backup.py") -Raw
$createdDatabase = $false

Push-Location $repoRoot
try {
    & (Join-Path $PSScriptRoot "restore-postgres.ps1") `
        -BackupPath $databaseBackup.FullName `
        -ComposeFile $ComposeFile `
        -TargetDatabase $databaseName `
        -IdentityPath $IdentityPath | Out-Null
    $createdDatabase = $true

    $databaseUser = (& $docker @composeArguments exec -T postgres printenv POSTGRES_USER).Trim()
    $validationSql = @"
SELECT CASE WHEN
    to_regclass('public.alembic_version') IS NOT NULL
    AND to_regclass('public.accounts') IS NOT NULL
    AND to_regclass('public.questions') IS NOT NULL
    AND to_regclass('public.question_feedback') IS NOT NULL
    AND to_regclass('public.admin_devices') IS NOT NULL
    AND (SELECT count(*) FROM public.location_samples) = 0
    AND (SELECT count(*) FROM public.together_device_health) = 0
    AND (SELECT count(*) FROM public.question_feedback) = 0
    AND (SELECT count(*) FROM public.question_feedback_operations) = 0
    AND (SELECT count(*) FROM public.anonymous_question_reviews) = 0
THEN 'ok' ELSE 'invalid' END;
"@
    $validation = & $docker @composeArguments exec -T postgres psql `
        --username=$databaseUser --dbname=$databaseName --no-align --tuples-only `
        --set=ON_ERROR_STOP=1 --command=$validationSql
    if ($LASTEXITCODE -ne 0 -or ("$validation").Trim() -ne "ok") {
        throw "The database restore did not satisfy the privacy and schema checks."
    }

    Invoke-BinaryPipeline `
        -SourceFile $age `
        -SourceArguments @("--decrypt", "--identity", $IdentityPath, $attachmentBackup.FullName) `
        -DestinationFile $docker `
        -DestinationArguments ($composeArguments + @(
            "run", "--rm", "-T", "--no-deps", "--entrypoint", "python",
            "attachment-init", "-c", $verifier))

    [ordered]@{
        created_at = (Get-Date).ToUniversalTime().ToString("o")
        database_schema = "verified"
        excluded_private_rows = "verified_empty"
        attachment_manifest = "verified"
        pair_manifest_sha256 = (Get-FileHash -LiteralPath $pairManifest.FullName -Algorithm SHA256).Hash.ToLowerInvariant()
        database_backup_sha256 = (Get-FileHash -LiteralPath $databaseBackup.FullName -Algorithm SHA256).Hash.ToLowerInvariant()
        attachment_backup_sha256 = (Get-FileHash -LiteralPath $attachmentBackup.FullName -Algorithm SHA256).Hash.ToLowerInvariant()
    } | ConvertTo-Json
}
finally {
    if ($createdDatabase) {
        if ($databaseName -notmatch '^little_orbit_drill_[0-9]{14}$') {
            throw "Refusing to remove an unexpected restore-drill database."
        }
        $databaseUser = (& $docker @composeArguments exec -T postgres printenv POSTGRES_USER).Trim()
        & $docker @composeArguments exec -T postgres dropdb `
            --username=$databaseUser --force --if-exists $databaseName | Out-Null
    }
    Pop-Location
}
