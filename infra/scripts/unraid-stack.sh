#!/usr/bin/env bash
set -euo pipefail

readonly SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
readonly DEPLOY_ROOT="${LITTLE_ORBIT_DEPLOY_ROOT:-/mnt/cache/little-orbit-deploy/repo}"
readonly ENV_FILE="${LITTLE_ORBIT_ENV_FILE:-/mnt/cache/little-orbit-secrets/runtime.env}"
readonly EXPECTED_DEPLOY_ROOT="/mnt/cache/little-orbit-deploy/repo"
readonly EXPECTED_ENV_FILE="/mnt/cache/little-orbit-secrets/runtime.env"
readonly -a FIXED_ENV_KEYS=(
  PUBLIC_BASE_URL GATEWAY_BIND_ADDRESS GATEWAY_INTERNAL_SUBNET
  GATEWAY_CADDY_IP GATEWAY_API_IP TRUSTED_PROXY_IP
  LITTLE_ORBIT_DATA_ROOT RELEASE_STORAGE_ROOT GPU_COORDINATOR_ROOT
  GPU_LOCK_HOST_PATH LITTLE_ORBIT_BACKUP_ROOT LITTLE_ORBIT_ENV_FILE
  GPU_LOCK_PATH AI_SCHEDULE_TIMEZONE
)
RUNTIME_ENV_KEYS=()

source "${SCRIPT_DIR}/unraid-operation-lock.sh"

read_env_value() {
  local key="$1"
  awk -F= -v wanted="${key}" '
    {
      name=$1
      gsub(/^[[:space:]]+|[[:space:]]+$/, "", name)
    }
    name == wanted {
      count++
      value=substr($0, index($0, "=") + 1)
      sub(/\r$/, "", value)
      gsub(/^[[:space:]]+|[[:space:]]+$/, "", value)
      if (value ~ /^".*"$/) value=substr(value, 2, length(value) - 2)
      found=value
    }
    END { if (count != 1 || found == "") exit 1; print found }
  ' "${ENV_FILE}"
}

require_fixed_setting() {
  local key="$1" expected="$2" value
  value="$(read_env_value "${key}")" || {
    echo "Required fixed Unraid setting is missing: ${key}" >&2
    exit 78
  }
  [[ "${value}" == "${expected}" ]] || {
    echo "Fixed Unraid setting does not match the reviewed target: ${key}" >&2
    exit 78
  }
}

reject_runtime_control_keys() {
  if awk -F= '
    {
      name=$1
      gsub(/^[[:space:]]+|[[:space:]]+$/, "", name)
      if (name ~ /^(COMPOSE_|DOCKER_)/) exit 1
    }
  ' "${ENV_FILE}"; then
    return 0
  fi
  echo "Docker and Compose control variables are forbidden in runtime.env." >&2
  exit 78
}

inventory_runtime_keys() {
  local raw trimmed name
  local -A seen=()
  RUNTIME_ENV_KEYS=()
  while IFS= read -r raw || [[ -n "${raw}" ]]; do
    raw="${raw%$'\r'}"
    trimmed="${raw#"${raw%%[![:space:]]*}"}"
    [[ -z "${trimmed}" || "${trimmed}" == \#* ]] && continue
    if [[ "${trimmed}" =~ ^export[[:space:]]+ ]]; then
      trimmed="${trimmed#export}"
      trimmed="${trimmed#"${trimmed%%[![:space:]]*}"}"
    fi
    [[ "${trimmed}" =~ ^([A-Za-z_][A-Za-z0-9_]*)[[:space:]]*= ]] || {
      echo "runtime.env contains a malformed definition." >&2
      exit 78
    }
    name="${BASH_REMATCH[1]}"
    [[ -z "${seen[${name}]:-}" ]] || {
      echo "runtime.env contains a duplicate definition: ${name}" >&2
      exit 78
    }
    seen["${name}"]=1
    RUNTIME_ENV_KEYS+=("${name}")
  done <"${ENV_FILE}"
}

sanitize_process_environment() {
  local name
  while IFS= read -r name; do
    case "${name}" in
      HOME|LANG|LC_*|LOGNAME|PATH|SHELL|TERM|TMPDIR|TZ|USER|LITTLE_ORBIT_MIGRATION_LOCK_TOKEN|LITTLE_ORBIT_OPERATIONS_LOCK_FD)
        ;;
      *) unset "${name}" ;;
    esac
  done < <(compgen -e)
  unset "${RUNTIME_ENV_KEYS[@]}"
  export LITTLE_ORBIT_ENV_FILE="${ENV_FILE}"
}

fix_local_docker_endpoint() {
  [[ -S /var/run/docker.sock && ! -L /var/run/docker.sock ]] || {
    echo "The local Unraid Docker socket is unavailable or unsafe." >&2
    exit 69
  }
  unset DOCKER_CONTEXT DOCKER_TLS_VERIFY DOCKER_CERT_PATH DOCKER_API_VERSION
  export DOCKER_HOST=unix:///var/run/docker.sock
  unset COMPOSE_FILE COMPOSE_PROJECT_NAME COMPOSE_PATH_SEPARATOR COMPOSE_PROFILES
  unset COMPOSE_ENV_FILES COMPOSE_DISABLE_ENV_FILE COMPOSE_PARALLEL_LIMIT
  unset COMPOSE_IGNORE_ORPHANS COMPOSE_REMOVE_ORPHANS COMPOSE_CONVERT_WINDOWS_PATHS
  unset COMPOSE_ANSI COMPOSE_STATUS_STDOUT COMPOSE_PROGRESS COMPOSE_MENU
  unset COMPOSE_EXPERIMENTAL COMPOSE_BAKE
}

if [[ ! -f "${DEPLOY_ROOT}/infra/compose.yaml" ]]; then
  echo "Little Orbit checkout is unavailable at the configured deploy root." >&2
  exit 66
fi
if [[ ! -f "${ENV_FILE}" ]]; then
  echo "Little Orbit runtime environment file is unavailable." >&2
  exit 66
fi
[[ "${DEPLOY_ROOT}" == "${EXPECTED_DEPLOY_ROOT}" && "${ENV_FILE}" == "${EXPECTED_ENV_FILE}" ]] || {
  echo "Little Orbit production paths must use the fixed Unraid roots." >&2
  exit 78
}
[[ ! -L "${DEPLOY_ROOT}" && ! -L "${ENV_FILE}"
  && "$(realpath -e "${DEPLOY_ROOT}")" == "${EXPECTED_DEPLOY_ROOT}"
  && "$(realpath -e "${ENV_FILE}")" == "${EXPECTED_ENV_FILE}" ]] || {
  echo "Little Orbit production paths cannot be symbolic links." >&2
  exit 78
}
[[ "$(stat -c '%F:%u:%g:%a:%h' "${ENV_FILE}")" == \
  "regular file:0:0:600:1" ]] || {
  echo "The runtime environment must remain root:root mode 0600." >&2
  exit 78
}
inventory_runtime_keys
reject_runtime_control_keys
require_fixed_setting PUBLIC_BASE_URL https://lil-orb.pax-kun.com
require_fixed_setting GATEWAY_BIND_ADDRESS 192.168.50.14
require_fixed_setting GATEWAY_INTERNAL_SUBNET 10.253.14.0/28
require_fixed_setting GATEWAY_CADDY_IP 10.253.14.2
require_fixed_setting GATEWAY_API_IP 10.253.14.3
require_fixed_setting TRUSTED_PROXY_IP 10.253.14.2
require_fixed_setting LITTLE_ORBIT_DATA_ROOT /mnt/cache/little-orbit-live
require_fixed_setting RELEASE_STORAGE_ROOT /mnt/cache/little-orbit-live/releases
require_fixed_setting GPU_COORDINATOR_ROOT /mnt/cache/gpu-coordinator
require_fixed_setting GPU_LOCK_HOST_PATH /mnt/cache/gpu-coordinator/gpu.lock
require_fixed_setting LITTLE_ORBIT_BACKUP_ROOT /mnt/user/little-orbit-backups
require_fixed_setting LITTLE_ORBIT_ENV_FILE "${EXPECTED_ENV_FILE}"
require_fixed_setting GPU_LOCK_PATH /run/gpu-coordinator/gpu.lock
require_fixed_setting AI_SCHEDULE_TIMEZONE America/Los_Angeles

# Docker Compose gives inherited process variables precedence over --env-file.
# Retain only process essentials and this migration's capability, then restore
# the single canonical env-file pointer. This also prevents optional settings
# omitted from runtime.env from being injected by an interactive shell.
sanitize_process_environment
fix_local_docker_endpoint
acquire_or_authorize_little_orbit_operations_lock wait 300 || {
  echo "Little Orbit lifecycle lock wait timed out or authorization failed." >&2
  exit 75
}

readonly -a COMPOSE=(
  docker compose
  --project-name little-orbit
  --project-directory "${DEPLOY_ROOT}/infra"
  --env-file "${ENV_FILE}"
  -f "${DEPLOY_ROOT}/infra/compose.yaml"
  -f "${DEPLOY_ROOT}/infra/compose.gpu.yaml"
  -f "${DEPLOY_ROOT}/infra/compose.unraid.yaml"
)

verify_effective_exposure_model() {
  command -v jq >/dev/null || {
    echo "jq is required to validate the effective Compose exposure model." >&2
    exit 69
  }
  "${COMPOSE[@]}" config --format json | jq -e \
    --arg address "192.168.50.14" --arg port "8180" '
      [.services | to_entries[] |
        (.value.ports // [])[] as $published |
        {service:.key, port:$published}] as $ports |
      ($ports | length) == 1 and
      $ports[0].service == "gateway" and
      ($ports[0].port.target | tostring) == $port and
      ($ports[0].port.published | tostring) == $port and
      $ports[0].port.host_ip == $address and
      ($ports[0].port.protocol // "tcp") == "tcp" and
      all(.services | to_entries[];
        (.value.network_mode // "") != "host")
    ' >/dev/null || {
      echo "The effective Compose model violates the single fixed gateway exposure." >&2
      exit 78
    }
}

verify_effective_exposure_model
if [[ "${1:-}" == "validate" ]]; then
  shift
  set -- config --quiet "$@"
fi
exec "${COMPOSE[@]}" "$@"
