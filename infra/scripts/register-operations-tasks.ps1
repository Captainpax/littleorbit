param(
    [string]$TaskPrefix = "Little Orbit",
    [string]$PowerShellExecutable = "powershell.exe"
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"
$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "../..")).Path
$runner = (Resolve-Path (Join-Path $PSScriptRoot "operations-runner.ps1")).Path
$identity = [Security.Principal.WindowsIdentity]::GetCurrent().Name
$settings = New-ScheduledTaskSettingsSet `
    -MultipleInstances IgnoreNew `
    -StartWhenAvailable `
    -ExecutionTimeLimit (New-TimeSpan -Hours 4)
$principal = New-ScheduledTaskPrincipal `
    -UserId $identity `
    -LogonType Interactive `
    -RunLevel Limited

function Register-LittleOrbitTask {
    param(
        [string]$Name,
        [string]$Mode,
        [Microsoft.Management.Infrastructure.CimInstance]$Trigger,
        [string]$Description
    )

    $arguments = "-NoProfile -NonInteractive -ExecutionPolicy Bypass -File `"$runner`" -Mode $Mode"
    $action = New-ScheduledTaskAction `
        -Execute $PowerShellExecutable `
        -Argument $arguments `
        -WorkingDirectory $repoRoot
    $task = New-ScheduledTask `
        -Action $action `
        -Trigger $Trigger `
        -Settings $settings `
        -Principal $principal `
        -Description $Description
    Register-ScheduledTask -TaskName "$TaskPrefix $Name" -InputObject $task `
        -Force -ErrorAction Stop | Out-Null
    Get-ScheduledTask -TaskName "$TaskPrefix $Name" -ErrorAction Stop | Out-Null
}

$daily = New-ScheduledTaskTrigger -Daily -At "06:00"
$weekly = New-ScheduledTaskTrigger -Weekly -WeeksInterval 1 -DaysOfWeek Tuesday -At "07:00"
$pending = New-ScheduledTaskTrigger `
    -Once `
    -At (Get-Date).AddMinutes(1) `
    -RepetitionInterval (New-TimeSpan -Minutes 5)

Register-LittleOrbitTask "Encrypted Backup" "backup" $daily `
    "Create the daily coordinated encrypted Little Orbit backup."
Register-LittleOrbitTask "Restore Drill" "test_restore" $weekly `
    "Verify the latest database and attachment backups without replacing live data."
Register-LittleOrbitTask "Admin Jobs" "pending" $pending `
    "Execute typed backup and restore requests from enrolled Big Orbit devices."

Write-Output "Registered Little Orbit operations tasks for $identity."
