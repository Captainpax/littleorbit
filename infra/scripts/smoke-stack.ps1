param(
    [ValidateSet("up", "down", "status")]
    [string]$Action = "status"
)

$ErrorActionPreference = "Stop"
$root = Resolve-Path (Join-Path $PSScriptRoot "..\..")
$files = @(
    "-f", (Join-Path $root "infra\compose.yaml"),
    "-f", (Join-Path $root "infra\compose.dev.yaml"),
    "-f", (Join-Path $root "infra\compose.smoke.yaml")
)

if ($Action -eq "up") {
    docker compose --env-file (Join-Path $root ".env") @files up -d --build `
        postgres attachment-init api clamav media-worker mailpit web gateway
    exit $LASTEXITCODE
}
if ($Action -eq "down") {
    docker compose --env-file (Join-Path $root ".env") @files down --volumes --remove-orphans
    exit $LASTEXITCODE
}
docker compose --env-file (Join-Path $root ".env") @files ps
exit $LASTEXITCODE
