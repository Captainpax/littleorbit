param(
    [Parameter(Mandatory = $true)][string]$BackupPath,
    [string]$ComposeFile = "infra/compose.yaml",
    [string]$IdentityPath = (Join-Path $env:LOCALAPPDATA "LittleOrbit/backup-age-identity.txt"),
    [switch]$ConfirmDestructive
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"
. (Join-Path $PSScriptRoot "lib/Invoke-BinaryPipeline.ps1")

if (-not $ConfirmDestructive) {
    throw "Attachment restore replaces current attachment bytes. Pass -ConfirmDestructive."
}
$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "../..")).Path
$resolvedBackup = (Resolve-Path -LiteralPath $BackupPath).Path
$repoPrefix = $repoRoot.TrimEnd([IO.Path]::DirectorySeparatorChar) + [IO.Path]::DirectorySeparatorChar
if (-not $resolvedBackup.StartsWith($repoPrefix, [StringComparison]::OrdinalIgnoreCase)) {
    throw "Restore file must be inside the Little Orbit workspace."
}
if ($resolvedBackup -notlike "*.tar.age") {
    throw "Restore requires an encrypted .tar.age backup."
}
if (-not (Test-Path -LiteralPath $IdentityPath -PathType Leaf)) {
    throw "The age identity file is unavailable."
}

$restoreScript = Get-Content -LiteralPath (Join-Path $PSScriptRoot "restore-attachment-backup.py") -Raw
$docker = (Get-Command docker -ErrorAction Stop).Source
$age = (Get-Command age -ErrorAction Stop).Source
$composeArguments = @("compose", "--env-file", ".env", "-f", $ComposeFile)
Push-Location $repoRoot
$serviceIds = @()
try {
    $serviceIds = @(& $docker @composeArguments ps -q --status running gateway api worker media-worker) |
        Where-Object { $_ }
    if (-not $serviceIds) {
        throw "No running attachment readers were found."
    }
    & $docker stop @serviceIds | Out-Null
    if ($LASTEXITCODE -ne 0) {
        throw "Could not stop attachment readers before restore."
    }
    Invoke-BinaryPipeline `
        -SourceFile $age `
        -SourceArguments @("--decrypt", "--identity", $IdentityPath, $resolvedBackup) `
        -DestinationFile $docker `
        -DestinationArguments ($composeArguments + @("run", "--rm", "-T", "--no-deps", "--entrypoint", "python", "attachment-init", "-c", $restoreScript))
    Write-Output $resolvedBackup
}
finally {
    if ($serviceIds) {
        & $docker start @serviceIds | Out-Null
    }
    Pop-Location
}
