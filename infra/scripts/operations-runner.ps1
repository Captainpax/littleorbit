param(
    [ValidateSet("pending", "backup", "test_restore")]
    [string]$Mode = "pending",
    [string]$ComposeFile = "infra/compose.yaml",
    [string]$IdentityPath = (Join-Path $env:LOCALAPPDATA "LittleOrbit/backup-age-identity.txt")
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"
$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "../..")).Path
$docker = (Get-Command docker -ErrorAction Stop).Source
$composeArguments = @("compose", "--env-file", ".env", "-f", $ComposeFile)
$mutex = [Threading.Mutex]::new($false, "Local\LittleOrbitOperationsRunner")
$lockAcquired = $false

function Invoke-DatabaseCommand {
    param([Parameter(Mandatory = $true)][string]$Sql)

    $databaseUser = (& $docker @composeArguments exec -T postgres printenv POSTGRES_USER).Trim()
    $databaseName = (& $docker @composeArguments exec -T postgres printenv POSTGRES_DB).Trim()
    $output = & $docker @composeArguments exec -T postgres psql `
        --username=$databaseUser --dbname=$databaseName --no-align --tuples-only `
        --set=ON_ERROR_STOP=1 --command=$Sql
    if ($LASTEXITCODE -ne 0) {
        throw "The operations database command failed."
    }
    return ("$output").Trim()
}

function ConvertTo-SqlJson {
    param([Parameter(Mandatory = $true)][hashtable]$Value)

    return (($Value | ConvertTo-Json -Compress).Replace("'", "''"))
}

function Start-RunRecord {
    param([string]$Kind, [string]$JobId)

    $runId = [Guid]::NewGuid().ToString()
    $jobValue = if ($JobId) { "'$JobId'::uuid" } else { "NULL" }
    $sql = @"
INSERT INTO backup_runs
    (id, job_request_id, kind, status, destination, details_json, created_at)
VALUES
    ('$runId'::uuid, $jobValue, '$Kind', 'running', 'local_encrypted', '{}'::json, now());
"@
    Invoke-DatabaseCommand $sql | Out-Null
    return $runId
}

function Complete-RunRecord {
    param(
        [string]$RunId,
        [string]$Status,
        [string]$ManifestDigest,
        [hashtable]$Details,
        [string]$Destination = "local_encrypted"
    )

    $json = ConvertTo-SqlJson $Details
    $digestValue = if ($ManifestDigest) { "'$ManifestDigest'" } else { "NULL" }
    Invoke-DatabaseCommand @"
UPDATE backup_runs
SET status = '$Status', destination = '$Destination', manifest_sha256 = $digestValue,
    details_json = '$json'::json, finished_at = now()
WHERE id = '$RunId'::uuid;
"@ | Out-Null
}

function Complete-Job {
    param([string]$JobId, [string]$Status, [hashtable]$Result)

    if (-not $JobId) {
        return
    }
    $json = ConvertTo-SqlJson $Result
    Invoke-DatabaseCommand @"
UPDATE admin_job_requests
SET status = '$Status', result_json = '$json'::json, finished_at = now()
WHERE id = '$JobId'::uuid AND status = 'running';
"@ | Out-Null
}

function Invoke-BackupOperation {
    param([string]$JobId)

    $runId = Start-RunRecord "backup" $JobId
    try {
        $raw = & (Join-Path $PSScriptRoot "backup-all.ps1") -ComposeFile $ComposeFile
        $result = (($raw | Out-String).Trim() | ConvertFrom-Json)
        $digest = (Get-FileHash -LiteralPath $result.pair_manifest -Algorithm SHA256).Hash.ToLowerInvariant()
        $databaseBytes = (Get-Item -LiteralPath $result.database).Length
        $attachmentBytes = (Get-Item -LiteralPath $result.attachments).Length
        $details = @{
            database_bytes = $databaseBytes
            attachment_bytes = $attachmentBytes
            off_host_copy = [bool]$result.off_host_copy
            coordinated_pair = $true
            private_feedback_included = $false
            raw_coordinates_included = $false
        }
        $destination = if ($result.off_host_copy) { "local_and_offhost" } else { "local_encrypted" }
        Complete-RunRecord $runId "passed" $digest $details $destination
        Complete-Job $JobId "passed" @{ outcome = "backup_completed" }
    }
    catch {
        Complete-RunRecord $runId "failed" "" @{ reason = "backup_failed" }
        Complete-Job $JobId "failed" @{ reason = "backup_failed" }
        throw
    }
}

function Invoke-RestoreDrill {
    param([string]$JobId)

    $runId = Start-RunRecord "test_restore" $JobId
    try {
        $raw = & (Join-Path $PSScriptRoot "test-restore-latest.ps1") `
            -ComposeFile $ComposeFile -IdentityPath $IdentityPath
        $result = (($raw | Out-String).Trim() | ConvertFrom-Json)
        $digest = [string]$result.pair_manifest_sha256
        $details = @{
            database_schema = "verified"
            excluded_private_rows = "verified_empty"
            attachment_manifest = "verified"
        }
        Complete-RunRecord $runId "passed" $digest $details
        Complete-Job $JobId "passed" @{ outcome = "restore_drill_completed" }
    }
    catch {
        Complete-RunRecord $runId "failed" "" @{ reason = "restore_drill_failed" }
        Complete-Job $JobId "failed" @{ reason = "restore_drill_failed" }
        throw
    }
}

function Get-PendingJob {
    $claimSql = @"
WITH candidate AS (
    SELECT id
    FROM admin_job_requests
    WHERE status = 'pending' AND kind IN ('backup', 'test_restore')
    ORDER BY created_at
    FOR UPDATE SKIP LOCKED
    LIMIT 1
)
UPDATE admin_job_requests AS jobs
SET status = 'running', started_at = now()
FROM candidate
WHERE jobs.id = candidate.id
RETURNING jobs.id::text || '|' || jobs.kind;
"@
    return Invoke-DatabaseCommand $claimSql
}

Push-Location $repoRoot
try {
    $lockAcquired = $mutex.WaitOne(0)
    if (-not $lockAcquired) {
        Write-Output '{"outcome":"already_running"}'
        return
    }
    $containerId = (& $docker @composeArguments ps -q postgres).Trim()
    if (-not $containerId) {
        throw "PostgreSQL is not running."
    }
    Invoke-DatabaseCommand @"
UPDATE admin_job_requests
SET status = 'failed', result_json = '{"reason":"runner_interrupted"}'::json, finished_at = now()
WHERE status = 'running' AND kind IN ('backup', 'test_restore')
    AND started_at < now() - interval '2 hours';
UPDATE backup_runs
SET status = 'failed', details_json = '{"reason":"runner_interrupted"}'::json, finished_at = now()
WHERE status = 'running' AND created_at < now() - interval '2 hours';
"@ | Out-Null

    if ($Mode -eq "backup") {
        Invoke-BackupOperation ""
    }
    elseif ($Mode -eq "test_restore") {
        Invoke-RestoreDrill ""
    }
    else {
        for ($index = 0; $index -lt 5; $index++) {
            $claimed = Get-PendingJob
            if (-not $claimed) {
                break
            }
            $parts = $claimed.Split('|')
            if ($parts.Length -ne 2 -or $parts[0] -notmatch '^[0-9a-f-]{36}$') {
                throw "The claimed operations job was malformed."
            }
            if ($parts[1] -eq "backup") {
                Invoke-BackupOperation $parts[0]
            }
            elseif ($parts[1] -eq "test_restore") {
                Invoke-RestoreDrill $parts[0]
            }
        }
    }
}
finally {
    Pop-Location
    if ($lockAcquired) {
        $mutex.ReleaseMutex()
    }
    $mutex.Dispose()
}
