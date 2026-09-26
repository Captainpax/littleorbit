param(
    [Parameter(Mandatory = $true)]
    [string]$Serial,
    [ValidateRange(0, 1)]
    [int]$AccountIndex = 0,
    [switch]$ResetApp
)

$ErrorActionPreference = "Stop"
$root = Resolve-Path (Join-Path $PSScriptRoot "..\..")
$attachmentTitlePath = Join-Path $root ".inspect\attachment-smoke-title.txt"
if (-not (Test-Path -LiteralPath $attachmentTitlePath)) {
    throw "Run create_attachment_smoke.py before the Android smoke test."
}
$attachmentTitle = (Get-Content -LiteralPath $attachmentTitlePath -Raw).Trim()
if (-not $attachmentTitle) { throw "The attachment smoke title is empty." }
$adb = Join-Path $env:LOCALAPPDATA "Android\Sdk\platform-tools\adb.exe"
$apk = Join-Path $root "apps\android\mobile\build\outputs\apk\smoke\mobile-smoke.apk"
$accountFile = Join-Path $root ".inspect\smoke-accounts.json"
$package = "com.littleorbit.mobile.smoke"

if (-not (Test-Path -LiteralPath $apk)) { throw "Build the smoke APK first." }
if (-not (Test-Path -LiteralPath $accountFile)) { throw "Create isolated smoke accounts first." }
$accounts = Get-Content -LiteralPath $accountFile | ConvertFrom-Json

function Get-Ui {
    $priorPreference = $ErrorActionPreference
    $ErrorActionPreference = "SilentlyContinue"
    & $adb -s $Serial shell rm -f /sdcard/little-orbit-smoke.xml 2>&1 | Out-Null
    & $adb -s $Serial shell uiautomator dump /sdcard/little-orbit-smoke.xml 2>&1 | Out-Null
    $dumpExitCode = $LASTEXITCODE
    if ($dumpExitCode -ne 0) { return $null }
    $raw = (& $adb -s $Serial shell cat /sdcard/little-orbit-smoke.xml) -join "`n"
    $ErrorActionPreference = $priorPreference
    $start = $raw.IndexOf("<?xml")
    if ($start -lt 0) { return $null }
    return [xml]$raw.Substring($start)
}

function Find-Node([string]$Text, [string]$IdSuffix) {
    $ui = Get-Ui
    if ($null -eq $ui) { return $null }
    foreach ($node in $ui.SelectNodes("//node")) {
        $visibility = $node.GetAttribute('visible-to-user')
        if ($visibility -and $visibility -ne 'true') { continue }
        if ($Text -and $node.text -eq $Text) { return $node }
        if ($IdSuffix -and $node.'resource-id'.EndsWith(":id/$IdSuffix")) { return $node }
    }
    return $null
}

function Wait-Node([string]$Text = "", [string]$IdSuffix = "", [int]$Attempts = 20) {
    for ($index = 0; $index -lt $Attempts; $index++) {
        $node = Find-Node $Text $IdSuffix
        if ($null -ne $node) { return $node }
        Start-Sleep -Milliseconds 500
    }
    throw "Expected UI node was unavailable (text='$Text', id='$IdSuffix')."
}

function Tap-Node($Node) {
    if ($Node.bounds -notmatch '\[(\d+),(\d+)\]\[(\d+),(\d+)\]') {
        throw "UI node bounds were invalid."
    }
    $x = ([int]$Matches[1] + [int]$Matches[3]) / 2
    $y = ([int]$Matches[2] + [int]$Matches[4]) / 2
    & $adb -s $Serial shell input tap $x $y | Out-Null
}

function Clear-TextField($Node) {
    Tap-Node $Node
    & $adb -s $Serial shell input keyevent KEYCODE_MOVE_END | Out-Null
    $deletes = 1..160 | ForEach-Object { "KEYCODE_DEL" }
    & $adb -s $Serial shell input keyevent $deletes | Out-Null
}

function Tap-Optional([string]$Text, [int]$Attempts = 8) {
    for ($index = 0; $index -lt $Attempts; $index++) {
        $node = Find-Node $Text ""
        if ($null -ne $node) {
            Tap-Node $node
            Start-Sleep -Milliseconds 500
            return $true
        }
        Start-Sleep -Milliseconds 500
    }
    return $false
}

function Get-InlineAttachmentCount {
    $priorPreference = $ErrorActionPreference
    $ErrorActionPreference = "SilentlyContinue"
    $files = @(& $adb -s $Serial shell run-as $package ls -1 cache/note-attachments 2>$null)
    $exitCode = $LASTEXITCODE
    $ErrorActionPreference = $priorPreference
    if ($exitCode -ne 0) { return 0 }
    return @($files | Where-Object { $_.Trim() }).Count
}

function Assert-NoPreviewFailures {
    $log = (& $adb -s $Serial logcat -d -v brief) -join "`n"
    if ($log -match 'MARKWON-IMAGE.*Error loading image' -or
            $log -match 'Attachment is unavailable') {
        throw "Inline attachment preview logged a private-image resolution failure."
    }
    if ($log -match 'FATAL EXCEPTION.*littleorbit') {
        throw "Little Orbit crashed during the document smoke path."
    }
}

& $adb -s $Serial wait-for-device | Out-Null
& $adb -s $Serial reverse tcp:18180 tcp:18180 | Out-Null
& $adb -s $Serial install -r $apk | Out-Null
if ($ResetApp) { & $adb -s $Serial shell pm clear $package | Out-Null }
& $adb -s $Serial shell monkey -p $package -c android.intent.category.LAUNCHER 1 | Out-Null
Start-Sleep -Seconds 1
Tap-Optional "Not now" 20 | Out-Null
Tap-Node (Wait-Node -Text "Sign in")
Clear-TextField (Wait-Node -IdSuffix "emailInput")
& $adb -s $Serial shell input text $accounts.accounts[$AccountIndex].email | Out-Null
Clear-TextField (Wait-Node -IdSuffix "passwordInput")
& $adb -s $Serial shell input text $accounts.password | Out-Null
Tap-Node (Wait-Node -IdSuffix "signInButton")
Start-Sleep -Seconds 2
Tap-Optional "Later" 20 | Out-Null
Wait-Node -Text "Your little orbit" | Out-Null
$drawerButton = Find-Node "" "openLeftDrawer"
if ($null -ne $drawerButton) {
    Tap-Node $drawerButton
    Start-Sleep -Seconds 1
}
Tap-Node (Wait-Node -Text "Our Space")
Start-Sleep -Seconds 1
Wait-Node -Text "A shared place for plans, lists, and little moments." | Out-Null
& $adb -s $Serial shell run-as $package rm -rf cache/note-attachments 2>$null | Out-Null
& $adb -s $Serial logcat -c | Out-Null
Tap-Node (Wait-Node -Text $attachmentTitle)
Wait-Node -Text "Attachments" | Out-Null
Wait-Node -Text "transparent.png" | Out-Null
$inlineCount = 0
for ($index = 0; $inlineCount -lt 2 -and $index -lt 20; $index++) {
    Start-Sleep -Milliseconds 500
    $inlineCount = Get-InlineAttachmentCount
}
if ($inlineCount -lt 2) { throw "Both inline attachment previews were not downloaded." }
Assert-NoPreviewFailures
$resultDir = Join-Path $root ".inspect\emulator-matrix"
New-Item -ItemType Directory -Force -Path $resultDir | Out-Null
& $adb -s $Serial shell screencap -p /sdcard/little-orbit-preview.png | Out-Null
& $adb -s $Serial pull /sdcard/little-orbit-preview.png `
    (Join-Path $resultDir "$Serial-space-preview.png") | Out-Null
Tap-Node (Wait-Node -Text "Edit")
Wait-Node -IdSuffix "formattingMoreButton" | Out-Null
$gif = Find-Node "transparent.gif" ""
$displaySize = (& $adb -s $Serial shell wm size) -join " "
if ($displaySize -notmatch '(\d+)x(\d+)') { throw "The emulator display size was unavailable." }
$swipeX = [math]::Round([int]$Matches[1] * 0.65)
$swipeStartY = [math]::Round([int]$Matches[2] * 0.75)
$swipeEndY = [math]::Round([int]$Matches[2] * 0.35)
for ($index = 0; $null -eq $gif -and $index -lt 4; $index++) {
    & $adb -s $Serial shell input swipe $swipeX $swipeStartY $swipeX $swipeEndY 300 | Out-Null
    Start-Sleep -Milliseconds 500
    $gif = Find-Node "transparent.gif" ""
}
if ($null -eq $gif) { throw "The second sanitized attachment was unavailable." }
Assert-NoPreviewFailures
& $adb -s $Serial shell screencap -p /sdcard/little-orbit-smoke.png | Out-Null
& $adb -s $Serial pull /sdcard/little-orbit-smoke.png (Join-Path $resultDir "$Serial-space.png") | Out-Null
Write-Output "$Serial passed paired Home, drawer, Our Space, inline Markdown, dock, and attachments smoke."
