#!/usr/bin/env bash
set -euo pipefail

readonly DEPLOY_ROOT="${LITTLE_ORBIT_DEPLOY_ROOT:-/mnt/cache/little-orbit-deploy/repo}"
readonly ENV_FILE="${LITTLE_ORBIT_ENV_FILE:-/mnt/cache/little-orbit-secrets/runtime.env}"

if [[ ! -f "${DEPLOY_ROOT}/infra/compose.yaml" ]]; then
  echo "Little Orbit checkout is unavailable at the configured deploy root." >&2
  exit 66
fi
if [[ ! -f "${ENV_FILE}" ]]; then
  echo "Little Orbit runtime environment file is unavailable." >&2
  exit 66
fi

export LITTLE_ORBIT_ENV_FILE="${ENV_FILE}"
exec docker compose \
  --project-name little-orbit \
  --project-directory "${DEPLOY_ROOT}/infra" \
  --env-file "${ENV_FILE}" \
  -f "${DEPLOY_ROOT}/infra/compose.yaml" \
  -f "${DEPLOY_ROOT}/infra/compose.gpu.yaml" \
  -f "${DEPLOY_ROOT}/infra/compose.unraid.yaml" \
  "$@"
