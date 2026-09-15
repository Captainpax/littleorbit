[CmdletBinding()]
param(
    [string]$EnvironmentFile = ".env.android-signing",
    [string]$OutputDirectory = "dist/android",
    [string]$ReuseWearApk
)

$ErrorActionPreference = "Stop"
$SigningNames = @(
    "ANDROID_SIGNING_STORE_FILE",
    "ANDROID_SIGNING_STORE_PASSWORD",
    "ANDROID_SIGNING_KEY_ALIAS",
    "ANDROID_SIGNING_KEY_PASSWORD"
)

function Import-AllowlistedEnvironment([string]$Path, [string[]]$Names) {
    foreach ($line in Get-Content -LiteralPath $Path) {
        if ($line -notmatch '^([A-Z0-9_]+)=(.*)$' -or $Matches[1] -notin $Names) {
            continue
        }
        $value = $Matches[2].Trim()
        if ($value.Length -ge 2 -and $value[0] -eq $value[-1] -and $value[0] -in @('"', "'")) {
            $value = $value.Substring(1, $value.Length - 2)
        }
        Set-Item -LiteralPath "Env:$($Matches[1])" -Value $value
    }
}

function Find-ApkSigner([string]$SdkRoot) {
    $buildTools = Get-ChildItem -LiteralPath (Join-Path $SdkRoot "build-tools") -Directory |
        Sort-Object { [version]$_.Name } -Descending
    foreach ($directory in $buildTools) {
        $candidate = Join-Path $directory.FullName "apksigner.bat"
        if (Test-Path -LiteralPath $candidate) {
            return $candidate
        }
    }
    throw "Android apksigner was not found under $SdkRoot."
}

function Find-Aapt([string]$SdkRoot) {
    $buildTools = Get-ChildItem -LiteralPath (Join-Path $SdkRoot "build-tools") -Directory |
        Sort-Object { [version]$_.Name } -Descending
    foreach ($directory in $buildTools) {
        $candidate = Join-Path $directory.FullName "aapt.exe"
        if (Test-Path -LiteralPath $candidate) { return $candidate }
    }
    throw "Android aapt was not found under $SdkRoot."
}

function Read-VersionCode([string]$Aapt, [string]$Apk) {
    $package = & $Aapt dump badging $Apk | Where-Object { $_ -match '^package:' } |
        Select-Object -First 1
    if ($package -notmatch "name='com.littleorbit.mobile' versionCode='([0-9]+)'") {
        throw "Wear APK package identity or version code is invalid."
    }
    return [int]$Matches[1]
}

function Publish-Apk(
    [string]$Source,
    [string]$Destination,
    [string]$ApkSigner
) {
    Copy-Item -LiteralPath $Source -Destination $Destination -Force
    $verification = & $ApkSigner verify --verbose --print-certs $Destination
    if ($LASTEXITCODE -ne 0) {
        throw "Signature verification failed for $Destination."
    }
    $verification | ForEach-Object { Write-Host $_ }
    $certificateLine = $verification | Where-Object { $_ -match 'certificate SHA-256 digest:' } |
        Select-Object -First 1
    if ($certificateLine -notmatch '([a-f0-9]{64})$') {
        throw "The signing certificate fingerprint was not reported for $Destination."
    }
    $hash = (Get-FileHash -LiteralPath $Destination -Algorithm SHA256).Hash.ToLowerInvariant()
    "$hash  $([IO.Path]::GetFileName($Destination))" |
        Set-Content -LiteralPath "$Destination.sha256" -Encoding ascii
    return [pscustomobject]@{
        ApkSha256 = $hash
        SizeBytes = (Get-Item -LiteralPath $Destination).Length
        CertificateSha256 = $Matches[1]
    }
}

$projectRoot = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot "../.."))
$environmentPath = if ([IO.Path]::IsPathRooted($EnvironmentFile)) {
    $EnvironmentFile
} else {
    Join-Path $projectRoot $EnvironmentFile
}
Import-AllowlistedEnvironment $environmentPath $SigningNames
$missing = $SigningNames | Where-Object {
    [string]::IsNullOrWhiteSpace([Environment]::GetEnvironmentVariable($_))
}
if ($missing) {
    throw "Missing Android signing settings: $($missing -join ', ')."
}
$storePath = [Environment]::GetEnvironmentVariable("ANDROID_SIGNING_STORE_FILE")
if (-not [IO.Path]::IsPathRooted($storePath)) {
    $storePath = Join-Path $projectRoot $storePath
}
$env:ANDROID_SIGNING_STORE_FILE = (Resolve-Path -LiteralPath $storePath).Path

$sdkRoot = if ($env:ANDROID_HOME) {
    $env:ANDROID_HOME
} elseif ($env:ANDROID_SDK_ROOT) {
    $env:ANDROID_SDK_ROOT
} else {
    Join-Path $env:LOCALAPPDATA "Android/Sdk"
}
$apkSigner = Find-ApkSigner $sdkRoot
$aapt = Find-Aapt $sdkRoot

Push-Location $projectRoot
try {
    $tasks = @(':apps:android:mobile:assembleRelease')
    if (-not $ReuseWearApk) { $tasks += ':apps:android:wear:assembleRelease' }
    & .\gradlew.bat @tasks
    if ($LASTEXITCODE -ne 0) {
        throw "Gradle release build failed."
    }
} finally {
    Pop-Location
}

$phoneMetadataPath = Join-Path $projectRoot "apps/android/mobile/build/outputs/apk/release/output-metadata.json"
$phoneMetadata = Get-Content -LiteralPath $phoneMetadataPath -Raw | ConvertFrom-Json
$versionName = $phoneMetadata.elements[0].versionName
$outputPath = Join-Path $projectRoot $OutputDirectory
New-Item -ItemType Directory -Path $outputPath -Force | Out-Null

$phoneSource = Join-Path $projectRoot "apps/android/mobile/build/outputs/apk/release/mobile-release.apk"
$wearSource = if ($ReuseWearApk) {
    $candidate = if ([IO.Path]::IsPathRooted($ReuseWearApk)) {
        $ReuseWearApk
    } else { Join-Path $projectRoot $ReuseWearApk }
    (Resolve-Path -LiteralPath $candidate).Path
} else {
    Join-Path $projectRoot "apps/android/wear/build/outputs/apk/release/wear-release.apk"
}
$wearVersionCode = if ($ReuseWearApk) {
    Read-VersionCode $aapt $wearSource
} else {
    $wearMetadataPath = Join-Path $projectRoot `
        "apps/android/wear/build/outputs/apk/release/output-metadata.json"
    $wearMetadata = Get-Content -LiteralPath $wearMetadataPath -Raw | ConvertFrom-Json
    if ($wearMetadata.elements[0].versionName -ne $versionName) {
        throw "Phone and Wear APKs have different version names."
    }
    [int]$wearMetadata.elements[0].versionCode
}
$phoneDestination = Join-Path $outputPath "little-orbit-$versionName.apk"
$wearDestination = Join-Path $outputPath "little-orbit-wear-$versionName.apk"
$phone = Publish-Apk $phoneSource $phoneDestination $apkSigner
$wear = Publish-Apk $wearSource $wearDestination $apkSigner
if ($phone.CertificateSha256 -ne $wear.CertificateSha256) {
    throw "Phone and Wear APKs were signed by different certificates."
}

$releaseManifest = [ordered]@{
    Version = $versionName
    PhoneVersionCode = $phoneMetadata.elements[0].versionCode
    WearVersionCode = $wearVersionCode
    PhoneApk = [IO.Path]::GetFileName($phoneDestination)
    PhoneSha256 = $phone.ApkSha256
    PhoneSizeBytes = $phone.SizeBytes
    WearApk = [IO.Path]::GetFileName($wearDestination)
    WearSha256 = $wear.ApkSha256
    WearSizeBytes = $wear.SizeBytes
    CertificateSha256 = $phone.CertificateSha256
    NotificationTransport = "self-hosted-wss-polling"
}
$releaseManifest | ConvertTo-Json |
    Set-Content -LiteralPath (Join-Path $outputPath "release-manifest.json") -Encoding utf8

[pscustomobject]@{
    Version = $releaseManifest.Version
    PhoneVersionCode = $releaseManifest.PhoneVersionCode
    WearVersionCode = $releaseManifest.WearVersionCode
    PhoneApk = $phoneDestination
    PhoneSha256 = $releaseManifest.PhoneSha256
    PhoneSizeBytes = $releaseManifest.PhoneSizeBytes
    WearApk = $wearDestination
    WearSha256 = $releaseManifest.WearSha256
    WearSizeBytes = $releaseManifest.WearSizeBytes
    CertificateSha256 = $releaseManifest.CertificateSha256
    Manifest = Join-Path $outputPath "release-manifest.json"
}
