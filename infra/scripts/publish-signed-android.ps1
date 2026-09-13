[CmdletBinding()]
param(
    [string]$ManifestPath = "dist/android/release-manifest.json",
    [string]$ReleaseNotesPath,
    [string]$GitHubReleaseUrl,
    [int]$MinimumAndroid = 29,
    [int]$WearMinimumAndroid = 30,
    [int]$MinimumSupportedVersionCode = 6,
    [string]$RequiredAfter,
    [switch]$Publish
)

$ErrorActionPreference = "Stop"

function Find-AndroidTool([string]$SdkRoot, [string]$Name) {
    $directories = Get-ChildItem -LiteralPath (Join-Path $SdkRoot "build-tools") -Directory |
        Sort-Object { [version]$_.Name } -Descending
    foreach ($directory in $directories) {
        $candidate = Join-Path $directory.FullName $Name
        if (Test-Path -LiteralPath $candidate) { return $candidate }
    }
    throw "$Name was not found under $SdkRoot."
}

function Require-ManifestFields([object]$Manifest) {
    $names = @(
        "Version", "PhoneVersionCode", "WearVersionCode", "PhoneApk", "PhoneSha256",
        "PhoneSizeBytes", "WearApk", "WearSha256", "WearSizeBytes", "CertificateSha256"
    )
    foreach ($name in $names) {
        if ($null -eq $Manifest.$name -or [string]::IsNullOrWhiteSpace("$($Manifest.$name)")) {
            throw "Release manifest is missing $name."
        }
    }
    if ($Manifest.Version -notmatch '^[0-9A-Za-z._-]{1,40}$') {
        throw "Release manifest version is unsafe."
    }
}

function Assert-Artifact([string]$Path, [long]$Size, [string]$Sha256) {
    $file = Get-Item -LiteralPath $Path
    if ($file.Length -ne $Size) { throw "Artifact byte count differs from the manifest." }
    $actual = (Get-FileHash -LiteralPath $Path -Algorithm SHA256).Hash.ToLowerInvariant()
    if ($actual -ne $Sha256.ToLowerInvariant()) {
        throw "Artifact SHA-256 differs from the manifest."
    }
}

function Read-ApkIdentity([string]$Aapt, [string]$Path) {
    $line = & $Aapt dump badging $Path | Where-Object { $_ -match '^package:' } |
        Select-Object -First 1
    if ($line -notmatch "name='([^']+)' versionCode='([0-9]+)'") {
        throw "APK package identity could not be read."
    }
    return [pscustomobject]@{ Package = $Matches[1]; VersionCode = [int]$Matches[2] }
}

function Read-ApkSigner([string]$ApkSigner, [string]$Path) {
    $result = & $ApkSigner verify --verbose --print-certs $Path
    if ($LASTEXITCODE -ne 0) { throw "APK signature verification failed." }
    $line = $result | Where-Object { $_ -match 'certificate SHA-256 digest:' } |
        Select-Object -First 1
    if ($line -notmatch '([a-f0-9]{64})$') { throw "APK signer was not reported." }
    return $Matches[1]
}

function Stage-Artifact([string]$Source, [string]$Destination, [string]$Sha256) {
    if (Test-Path -LiteralPath $Destination) {
        $existing = (Get-FileHash -LiteralPath $Destination -Algorithm SHA256).Hash.ToLowerInvariant()
        if ($existing -ne $Sha256.ToLowerInvariant()) {
            throw "A different staged artifact already uses this version."
        }
        return
    }
    Copy-Item -LiteralPath $Source -Destination $Destination
}

function Publish-Record([object]$Manifest, [string]$Notes, [string]$MirrorUrl) {
    $version = $Manifest.Version
    $arguments = @(
        "compose", "--env-file", ".env", "-f", "infra/compose.yaml", "exec", "-T", "api",
        "python", "-m", "little_orbit_api.cli", "publish-release",
        "--version", $version,
        "--version-code", "$($Manifest.PhoneVersionCode)",
        "--apk-url", "https://lil-orb.pax-kun.com/api/v1/releases/$version/apk",
        "--github-release-url", $MirrorUrl,
        "--sha256", $Manifest.PhoneSha256,
        "--size-bytes", "$($Manifest.PhoneSizeBytes)",
        "--package-name", "com.littleorbit.mobile",
        "--signer-sha256", $Manifest.CertificateSha256,
        "--wear-apk-url", "https://lil-orb.pax-kun.com/api/v1/releases/$version/wear-apk",
        "--wear-sha256", $Manifest.WearSha256,
        "--wear-size-bytes", "$($Manifest.WearSizeBytes)",
        "--wear-package-name", "com.littleorbit.mobile",
        "--wear-version-code", "$($Manifest.WearVersionCode)",
        "--wear-minimum-android", "$WearMinimumAndroid",
        "--minimum-android", "$MinimumAndroid",
        "--minimum-supported-version-code", "$MinimumSupportedVersionCode",
        "--release-notes", $Notes
    )
    if ($RequiredAfter) { $arguments += @("--required-after", $RequiredAfter) }
    & docker @arguments
    if ($LASTEXITCODE -ne 0) { throw "Release publication failed." }
}

$projectRoot = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot "../.."))
$manifestFile = if ([IO.Path]::IsPathRooted($ManifestPath)) {
    $ManifestPath
} else {
    Join-Path $projectRoot $ManifestPath
}
$manifestFile = (Resolve-Path -LiteralPath $manifestFile).Path
$manifest = Get-Content -LiteralPath $manifestFile -Raw | ConvertFrom-Json
Require-ManifestFields $manifest

$artifactDirectory = Split-Path -Parent $manifestFile
$phoneSource = (Resolve-Path -LiteralPath (Join-Path $artifactDirectory $manifest.PhoneApk)).Path
$wearSource = (Resolve-Path -LiteralPath (Join-Path $artifactDirectory $manifest.WearApk)).Path
Assert-Artifact $phoneSource $manifest.PhoneSizeBytes $manifest.PhoneSha256
Assert-Artifact $wearSource $manifest.WearSizeBytes $manifest.WearSha256

$sdkRoot = if ($env:ANDROID_HOME) { $env:ANDROID_HOME } elseif ($env:ANDROID_SDK_ROOT) {
    $env:ANDROID_SDK_ROOT
} else { Join-Path $env:LOCALAPPDATA "Android/Sdk" }
$aapt = Find-AndroidTool $sdkRoot "aapt.exe"
$apkSigner = Find-AndroidTool $sdkRoot "apksigner.bat"
$phoneIdentity = Read-ApkIdentity $aapt $phoneSource
$wearIdentity = Read-ApkIdentity $aapt $wearSource
if ($phoneIdentity.Package -ne "com.littleorbit.mobile" -or
        $phoneIdentity.VersionCode -ne $manifest.PhoneVersionCode) {
    throw "Phone APK identity differs from the release manifest."
}
if ($wearIdentity.Package -ne "com.littleorbit.mobile" -or
        $wearIdentity.VersionCode -ne $manifest.WearVersionCode) {
    throw "Wear APK identity differs from the release manifest."
}
$phoneSigner = Read-ApkSigner $apkSigner $phoneSource
$wearSigner = Read-ApkSigner $apkSigner $wearSource
if ($phoneSigner -ne $manifest.CertificateSha256 -or $wearSigner -ne $phoneSigner) {
    throw "APK signing identity differs from the release manifest."
}

$stageDirectory = Join-Path $projectRoot "data/releases"
New-Item -ItemType Directory -Path $stageDirectory -Force | Out-Null
$phoneDestination = Join-Path $stageDirectory "little-orbit-$($manifest.Version).apk"
$wearDestination = Join-Path $stageDirectory "little-orbit-wear-$($manifest.Version).apk"
Stage-Artifact $phoneSource $phoneDestination $manifest.PhoneSha256
Stage-Artifact $wearSource $wearDestination $manifest.WearSha256

$published = $false
if ($Publish) {
    if ([string]::IsNullOrWhiteSpace($ReleaseNotesPath)) {
        throw "ReleaseNotesPath is required with -Publish."
    }
    $notesFile = if ([IO.Path]::IsPathRooted($ReleaseNotesPath)) {
        $ReleaseNotesPath
    } else { Join-Path $projectRoot $ReleaseNotesPath }
    $notes = (Get-Content -LiteralPath $notesFile -Raw).Trim()
    if (-not $notes) { throw "Release notes are empty." }
    $mirror = if ($GitHubReleaseUrl) { $GitHubReleaseUrl } else {
        "https://github.com/Captainpax/littleorbit/releases/tag/v$($manifest.Version)"
    }
    Push-Location $projectRoot
    try { Publish-Record $manifest $notes $mirror } finally { Pop-Location }
    $published = $true
}

[pscustomobject]@{
    Version = $manifest.Version
    PhoneVersionCode = $manifest.PhoneVersionCode
    WearVersionCode = $manifest.WearVersionCode
    PhoneSha256 = $manifest.PhoneSha256
    WearSha256 = $manifest.WearSha256
    Staged = $true
    Published = $published
}
