[CmdletBinding()]
param(
    [string]$PairAddress,
    [string]$ConnectAddress,
    [string]$ReleaseApi = "https://lil-orb.pax-kun.com/api/v1/releases/current"
)

$ErrorActionPreference = "Stop"
$ExpectedHost = "lil-orb.pax-kun.com"
$ExpectedPackage = "com.littleorbit.mobile"
$PinnedSigner = "43e83a420c7496ce9121339ab5bd6b01a6357161a83a95042ace56855bd89337"

function Find-AndroidTool([string]$Name) {
    $command = Get-Command "$Name.exe" -ErrorAction SilentlyContinue
    if ($command) { return $command.Source }
    $roots = @($env:ANDROID_HOME, $env:ANDROID_SDK_ROOT, "$env:LOCALAPPDATA\Android\Sdk") |
        Where-Object { $_ -and (Test-Path -LiteralPath $_) } |
        Select-Object -Unique
    foreach ($root in $roots) {
        if ($Name -eq "adb") {
            $candidate = Join-Path $root "platform-tools\adb.exe"
            if (Test-Path -LiteralPath $candidate) { return $candidate }
        } else {
            $tool = Get-ChildItem -LiteralPath (Join-Path $root "build-tools") -Directory |
                Sort-Object { [version]$_.Name } -Descending |
                ForEach-Object { Join-Path $_.FullName "$Name.exe" } |
                Where-Object { Test-Path -LiteralPath $_ } |
                Select-Object -First 1
            if ($tool) { return $tool }
        }
    }
    throw "$Name was not found. Install Android SDK Platform Tools and Build Tools first."
}

function Require-Endpoint([uri]$Uri, [string]$Version) {
    $expectedPath = "/api/v1/releases/$Version/wear-apk"
    if ($Uri.Scheme -ne "https" -or $Uri.Host -ne $ExpectedHost -or
        $Uri.Port -ne 443 -or $Uri.AbsolutePath -ne $expectedPath -or
        $Uri.Query -or $Uri.Fragment) {
        throw "Release metadata did not use the expected Little Orbit Wear endpoint."
    }
}

function Require-Address([string]$Value, [string]$Label) {
    if ($Value -notmatch '^[0-9A-Fa-f.:[\]-]+:\d{1,5}$') {
        throw "$Label must be the address shown by Wear OS wireless debugging."
    }
}

$releaseUri = [uri]$ReleaseApi
if ($releaseUri.Scheme -ne "https" -or $releaseUri.Host -ne $ExpectedHost -or
    $releaseUri.Port -ne 443 -or $releaseUri.AbsolutePath -ne "/api/v1/releases/current" -or
    $releaseUri.Query -or $releaseUri.Fragment) {
    throw "Release metadata must come from the Little Orbit current-release endpoint."
}
$metadata = Invoke-RestMethod -Uri $releaseUri -Method Get
$required = @(
    "version", "wear_apk_url", "wear_sha256", "wear_size_bytes",
    "wear_package_name", "wear_version_code", "signer_sha256"
)
foreach ($field in $required) {
    if (-not $metadata.$field) { throw "The current release is missing $field." }
}
if ($metadata.wear_package_name -ne $ExpectedPackage) {
    throw "The published Wear package is not Little Orbit."
}
if ([string]$metadata.signer_sha256 -cne $PinnedSigner) {
    throw "Published signing metadata did not match the pinned Little Orbit certificate."
}
$wearUri = [uri]$metadata.wear_apk_url
Require-Endpoint $wearUri $metadata.version

$adb = Find-AndroidTool "adb"
$aapt = Find-AndroidTool "aapt"
$apkSigner = Find-AndroidTool "apksigner"
$temporaryRoot = Join-Path ([IO.Path]::GetTempPath()) ("little-orbit-wear-" + [guid]::NewGuid())
$apkPath = Join-Path $temporaryRoot "little-orbit-wear.apk"
New-Item -ItemType Directory -Path $temporaryRoot | Out-Null

try {
    Write-Host "Downloading signed Little Orbit Wear $($metadata.version)..."
    Invoke-WebRequest -Uri $wearUri -OutFile $apkPath
    $file = Get-Item -LiteralPath $apkPath
    if ($file.Length -ne [long]$metadata.wear_size_bytes) {
        throw "Wear APK byte count did not match published metadata."
    }
    $digest = (Get-FileHash -LiteralPath $apkPath -Algorithm SHA256).Hash.ToLowerInvariant()
    if ($digest -cne [string]$metadata.wear_sha256) {
        throw "Wear APK SHA-256 did not match published metadata."
    }

    $badging = & $aapt dump badging $apkPath
    if ($LASTEXITCODE -ne 0) { throw "Android could not inspect the Wear APK package." }
    $packageLine = $badging | Where-Object { $_ -match '^package:' } | Select-Object -First 1
    if ($packageLine -notmatch "name='$([regex]::Escape($ExpectedPackage))'") {
        throw "Wear APK package name did not match Little Orbit."
    }
    if ($packageLine -notmatch "versionCode='$([regex]::Escape([string]$metadata.wear_version_code))'") {
        throw "Wear APK version code did not match published metadata."
    }

    $certificate = & $apkSigner verify --print-certs $apkPath
    if ($LASTEXITCODE -ne 0) { throw "Wear APK signature verification failed." }
    $certificateLine = $certificate |
        Where-Object { $_ -match 'certificate SHA-256 digest:' } |
        Select-Object -First 1
    if ($certificateLine -notmatch '([a-f0-9]{64})$' -or
        $Matches[1] -cne $PinnedSigner) {
        throw "Wear APK signing certificate did not match the pinned release certificate."
    }

    if (-not $PairAddress) { $PairAddress = Read-Host "Watch pairing address (IP:port)" }
    if (-not $ConnectAddress) { $ConnectAddress = Read-Host "Watch connection address (IP:port)" }
    Require-Address $PairAddress "Pairing address"
    Require-Address $ConnectAddress "Connection address"
    & $adb pair $PairAddress
    if ($LASTEXITCODE -ne 0) { throw "Wireless ADB pairing failed." }
    & $adb connect $ConnectAddress
    if ($LASTEXITCODE -ne 0) { throw "Wireless ADB connection failed." }
    $characteristics = & $adb -s $ConnectAddress shell getprop ro.build.characteristics
    if ($LASTEXITCODE -ne 0 -or $characteristics -notmatch 'watch') {
        throw "The connected Android device did not identify itself as a watch."
    }
    & $adb -s $ConnectAddress install -r $apkPath
    if ($LASTEXITCODE -ne 0) { throw "Wear OS rejected the verified APK installation." }
    Write-Host "Little Orbit is installed on the connected watch."
} finally {
    if (Test-Path -LiteralPath $temporaryRoot) {
        Remove-Item -LiteralPath $temporaryRoot -Recurse -Force
    }
}
