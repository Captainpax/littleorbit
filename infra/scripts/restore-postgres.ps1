param(
    [Parameter(Mandatory = $true)][string]$BackupPath,
    [string]$ComposeFile = "infra/compose.yaml",
    [string]$TargetDatabase = "",
    [string]$IdentityPath = (Join-Path $env:LOCALAPPDATA "LittleOrbit/backup-age-identity.txt"),
    [switch]$ConfirmDestructive
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"
. (Join-Path $PSScriptRoot "lib/Invoke-BinaryPipeline.ps1")

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "../..")).Path
$resolvedBackup = (Resolve-Path -LiteralPath $BackupPath).Path
$repoPrefix = $repoRoot.TrimEnd([IO.Path]::DirectorySeparatorChar) + [IO.Path]::DirectorySeparatorChar
if (-not $resolvedBackup.StartsWith($repoPrefix, [StringComparison]::OrdinalIgnoreCase)) {
    throw "Restore file must be inside the Little Orbit workspace."
}
if ($resolvedBackup -notlike "*.dump.age") {
    throw "Restore requires an encrypted .dump.age backup."
}
if (-not (Test-Path -LiteralPath $IdentityPath -PathType Leaf)) {
    throw "The age identity file is unavailable."
}
if ($TargetDatabase -and $TargetDatabase -notmatch '^[a-zA-Z][a-zA-Z0-9_]{0,62}$') {
    throw "Target database must be a simple PostgreSQL identifier."
}

$docker = (Get-Command docker -ErrorAction Stop).Source
$age = (Get-Command age -ErrorAction Stop).Source
$composeArguments = @("compose", "--env-file", ".env", "-f", $ComposeFile)
Push-Location $repoRoot
try {
    $containerId = (& $docker @composeArguments ps -q postgres).Trim()
    if (-not $containerId) {
        throw "PostgreSQL container is not running."
    }
    $databaseName = $TargetDatabase
    if (-not $databaseName) {
        if (-not $ConfirmDestructive) {
            throw "Restoring the active database requires -ConfirmDestructive."
        }
        $databaseName = (& $docker @composeArguments exec -T postgres printenv POSTGRES_DB).Trim()
    }
    $databaseUser = (& $docker @composeArguments exec -T postgres printenv POSTGRES_USER).Trim()
    $existsOutput = & $docker @composeArguments exec -T postgres psql --username=$databaseUser --dbname=postgres --tuples-only --no-align --command="SELECT 1 FROM pg_database WHERE datname = '$databaseName'"
    $exists = ("$existsOutput").Trim()
    if (-not $exists) {
        & $docker @composeArguments exec -T postgres createdb --username=$databaseUser $databaseName
        if ($LASTEXITCODE -ne 0) {
            throw "Could not create the restore database."
        }
    }
    Invoke-BinaryPipeline `
        -SourceFile $age `
        -SourceArguments @("--decrypt", "--identity", $IdentityPath, $resolvedBackup) `
        -DestinationFile $docker `
        -DestinationArguments ($composeArguments + @("exec", "-T", "postgres", "pg_restore", "--clean", "--if-exists", "--no-owner", "--username=$databaseUser", "--dbname=$databaseName"))
    Write-Output $databaseName
}
finally {
    Pop-Location
}
