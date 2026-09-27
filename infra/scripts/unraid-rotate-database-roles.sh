#!/usr/bin/env bash
set -euo pipefail

if [[ "$-" == *x* ]]; then
  echo "Database-role rotation refuses shell tracing." >&2
  exit 78
fi

readonly SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
readonly STACK="${SCRIPT_DIR}/unraid-stack.sh"
readonly FIREWALL="${SCRIPT_DIR}/unraid-firewall.sh"
readonly SECRET_ROOT="/mnt/cache/little-orbit-secrets"
readonly ENV_FILE="${SECRET_ROOT}/runtime.env"
readonly JOURNAL_FILE="${SECRET_ROOT}/database-role-rotation.state"
readonly OLD_ENV_PATH="${SECRET_ROOT}/.database-role-rotation.old.env"
readonly NEW_ENV_PATH="${SECRET_ROOT}/.database-role-rotation.new.env"
readonly RUNTIME_TEMP_PATH="${SECRET_ROOT}/.database-role-rotation.runtime.env"
readonly -a PASSWORD_KEYS=(POSTGRES_API_PASSWORD POSTGRES_WORKER_PASSWORD \
  POSTGRES_MEDIA_PASSWORD POSTGRES_BACKUP_PASSWORD)
readonly -a ROLE_NAMES=(little_orbit_api little_orbit_worker \
  little_orbit_media little_orbit_backup)
readonly -a URL_KEYS=(DATABASE_API_URL DATABASE_WORKER_URL DATABASE_MEDIA_URL)

declare -A NEW_PASSWORDS=()
ROTATION_ID=""
JOURNAL_STATE="absent"
OLD_ENV=""
NEW_ENV=""
ROLLBACK_ARMED=false

source "${SCRIPT_DIR}/unraid-operation-lock.sh"

stack() {
  bash "${STACK}" "$@"
}

firewall() {
  bash "${FIREWALL}" "$@"
}

secure_file() {
  local path="$1"
  [[ -f "${path}" && ! -L "${path}" \
    && "$(stat -c '%u:%g:%a:%h' "${path}")" == "0:0:600:1" ]]
}

read_env_value_from() {
  local path="$1" key="$2"
  awk -F= -v wanted="${key}" '
    {
      name=$1
      sub(/^[[:space:]]*export[[:space:]]+/, "", name)
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
  ' "${path}"
}

env_definition_key() {
  local value="$1"
  value="${value%$'\r'}"
  value="${value#"${value%%[![:space:]]*}"}"
  if [[ "${value}" =~ ^(export[[:space:]]+)?([A-Za-z_][A-Za-z0-9_]*)[[:space:]]*= ]]; then
    printf '%s' "${BASH_REMATCH[2]}"
  fi
}

validate_role_url() {
  local path="$1" key="$2" role="$3" database="$4"
  local value prefix suffix password_part
  value="$(read_env_value_from "${path}" "${key}")" || return 78
  prefix="postgresql+asyncpg://${role}:"
  suffix="@postgres:5432/${database}"
  [[ "${value}" == "${prefix}"*"${suffix}" ]] || return 78
  password_part="${value#"${prefix}"}"
  password_part="${password_part%"${suffix}"}"
  [[ -n "${password_part}" && "${password_part}" != *"@"* ]]
}

validate_runtime_values() {
  local path="$1" key database
  database="$(read_env_value_from "${path}" POSTGRES_DB)" || return 78
  [[ "${database}" == little_orbit ]] || return 78
  [[ "$(read_env_value_from "${path}" POSTGRES_USER)" == little_orbit ]] || return 78
  read_env_value_from "${path}" POSTGRES_PASSWORD >/dev/null || return 78
  for key in "${PASSWORD_KEYS[@]}"; do
    read_env_value_from "${path}" "${key}" >/dev/null || return 78
  done
  validate_role_url "${path}" DATABASE_OWNER_URL little_orbit "${database}" || return
  validate_role_url "${path}" DATABASE_API_URL little_orbit_api "${database}" || return
  validate_role_url "${path}" DATABASE_WORKER_URL little_orbit_worker "${database}" || return
  validate_role_url "${path}" DATABASE_MEDIA_URL little_orbit_media "${database}"
}

require_target() {
  [[ "$(id -u)" == 0 ]] || {
    echo "Database-role rotation must run as root." >&2
    return 77
  }
  command -v awk >/dev/null
  command -v flock >/dev/null
  command -v mktemp >/dev/null
  command -v openssl >/dev/null
  command -v realpath >/dev/null
  command -v stat >/dev/null
  command -v sync >/dev/null
  [[ -d "${SECRET_ROOT}" && ! -L "${SECRET_ROOT}" \
    && "$(realpath -e "${SECRET_ROOT}")" == "${SECRET_ROOT}" \
    && "$(stat -c '%F:%u:%g:%a' "${SECRET_ROOT}")" == "directory:0:0:700" ]] || {
    echo "The fixed Little Orbit secrets directory is unsafe." >&2
    return 78
  }
  secure_file "${ENV_FILE}" || {
    echo "runtime.env must be a root-owned mode-0600 single-link file." >&2
    return 78
  }
  [[ "$(realpath -e "${ENV_FILE}")" == "${ENV_FILE}" ]] || return 78
  validate_runtime_values "${ENV_FILE}" || {
    echo "runtime.env has an invalid database credential layout." >&2
    return 78
  }
}

create_secure_empty() {
  local path="$1"
  [[ ! -e "${path}" && ! -L "${path}" ]] || return 73
  (umask 077; set -o noclobber; : >"${path}") || return 73
  chown 0:0 "${path}" || return
  chmod 0600 "${path}" || return
  secure_file "${path}"
}

create_secure_copy() {
  local source="$1" destination="$2"
  create_secure_empty "${destination}" || return
  cp -- "${source}" "${destination}" || return
  chown 0:0 "${destination}" || return
  chmod 0600 "${destination}" || return
  sync -f "${destination}" || return
  secure_file "${destination}"
}

load_journal() {
  local -a lines=()
  JOURNAL_STATE="absent"
  ROTATION_ID=""
  if [[ ! -e "${JOURNAL_FILE}" && ! -L "${JOURNAL_FILE}" ]]; then
    return 0
  fi
  secure_file "${JOURNAL_FILE}" || return 78
  mapfile -t lines <"${JOURNAL_FILE}"
  ((${#lines[@]} == 3)) || return 78
  [[ "${lines[0]}" == "schema=1" ]] || return 78
  [[ "${lines[1]}" =~ ^operation_id=([0-9a-f]{32})$ ]] || return 78
  ROTATION_ID="${BASH_REMATCH[1]}"
  [[ "${lines[2]}" =~ ^state=(preparing|committed|rolled-back)$ ]] || return 78
  JOURNAL_STATE="${BASH_REMATCH[1]}"
}

write_journal() {
  local state="$1" temporary status=0
  [[ "${ROTATION_ID}" =~ ^[0-9a-f]{32}$ \
    && "${state}" =~ ^(preparing|committed|rolled-back)$ ]] || return 64
  [[ ! -L "${JOURNAL_FILE}" ]] || return 78
  temporary="$(mktemp -- "${SECRET_ROOT}/.database-role-rotation-state.XXXXXX")"
  chown 0:0 "${temporary}" || status=$?
  ((status == 0)) && chmod 0600 "${temporary}" || status=$?
  if ((status == 0)); then
    printf 'schema=1\noperation_id=%s\nstate=%s\n' \
      "${ROTATION_ID}" "${state}" >"${temporary}" || status=$?
  fi
  ((status == 0)) && sync -f "${temporary}" || status=$?
  ((status == 0)) && mv -T -- "${temporary}" "${JOURNAL_FILE}" || status=$?
  if ((status != 0)); then
    : >"${temporary}" 2>/dev/null || status=70
    rm -f -- "${temporary}" || status=70
    return "${status}"
  fi
  sync -f "${SECRET_ROOT}" && secure_file "${JOURNAL_FILE}"
}

stage_paths_for_id() {
  [[ "${ROTATION_ID}" =~ ^[0-9a-f]{32}$ ]] || return 64
  OLD_ENV="${OLD_ENV_PATH}"
  NEW_ENV="${NEW_ENV_PATH}"
}

generate_passwords() {
  local key value seen=":"
  NEW_PASSWORDS=()
  for key in "${PASSWORD_KEYS[@]}"; do
    value="$(openssl rand -hex 32)" || return 69
    [[ "${value}" =~ ^[0-9a-f]{64}$ ]] || return 69
    [[ "${seen}" != *":${value}:"* ]] || return 69
    NEW_PASSWORDS["${key}"]="${value}"
    seen="${seen}${value}:"
  done
}

replacement_line() {
  local key="$1"
  case "${key}" in
    POSTGRES_API_PASSWORD|POSTGRES_WORKER_PASSWORD|POSTGRES_MEDIA_PASSWORD|POSTGRES_BACKUP_PASSWORD)
      printf '%s=%s\n' "${key}" "${NEW_PASSWORDS[${key}]}"
      ;;
    DATABASE_API_URL)
      printf '%s=%s\n' "${key}" \
        "postgresql+asyncpg://little_orbit_api:${NEW_PASSWORDS[POSTGRES_API_PASSWORD]}@postgres:5432/little_orbit"
      ;;
    DATABASE_WORKER_URL)
      printf '%s=%s\n' "${key}" \
        "postgresql+asyncpg://little_orbit_worker:${NEW_PASSWORDS[POSTGRES_WORKER_PASSWORD]}@postgres:5432/little_orbit"
      ;;
    DATABASE_MEDIA_URL)
      printf '%s=%s\n' "${key}" \
        "postgresql+asyncpg://little_orbit_media:${NEW_PASSWORDS[POSTGRES_MEDIA_PASSWORD]}@postgres:5432/little_orbit"
      ;;
    *) return 1 ;;
  esac
}

render_rotated_env() {
  local source="$1" destination="$2" line key required
  local -A replaced=()
  [[ -f "${source}" && ! -L "${source}" \
    && -f "${destination}" && ! -L "${destination}" ]] || return 78
  : >"${destination}"
  while IFS= read -r line || [[ -n "${line}" ]]; do
    line="${line%$'\r'}"
    key="$(env_definition_key "${line}")"
    if [[ -n "${key}" ]] && replacement_line "${key}" >>"${destination}"; then
      [[ -z "${replaced[${key}]:-}" ]] || return 78
      replaced["${key}"]=1
    else
      printf '%s\n' "${line}" >>"${destination}"
    fi
  done <"${source}"
  for required in "${PASSWORD_KEYS[@]}" "${URL_KEYS[@]}"; do
    [[ "${replaced[${required}]:-}" == 1 ]] || return 78
  done
}

verify_passwords_changed() {
  local key old_value
  for key in "${PASSWORD_KEYS[@]}"; do
    old_value="$(read_env_value_from "${OLD_ENV}" "${key}")" || return 78
    [[ "${NEW_PASSWORDS[${key}]}" != "${old_value}" ]] || return 69
  done
}

prepare_new_rotation() {
  load_journal || {
    echo "The database-role rotation journal is invalid." >&2
    return 78
  }
  if [[ "${JOURNAL_STATE}" == preparing ]]; then
    echo "An interrupted rotation requires the recover command." >&2
    return 75
  fi
  if [[ -e "${OLD_ENV_PATH}" || -L "${OLD_ENV_PATH}" \
    || -e "${NEW_ENV_PATH}" || -L "${NEW_ENV_PATH}" \
    || -e "${RUNTIME_TEMP_PATH}" || -L "${RUNTIME_TEMP_PATH}" ]]; then
    echo "A prior credential snapshot requires operator cleanup." >&2
    return 78
  fi
  ROTATION_ID="$(openssl rand -hex 16)"
  [[ "${ROTATION_ID}" =~ ^[0-9a-f]{32}$ ]] || return 69
  stage_paths_for_id
  create_secure_copy "${ENV_FILE}" "${OLD_ENV}"
  create_secure_empty "${NEW_ENV}"
  generate_passwords
  verify_passwords_changed
  render_rotated_env "${OLD_ENV}" "${NEW_ENV}"
  chown 0:0 "${NEW_ENV}"; chmod 0600 "${NEW_ENV}"; sync -f "${NEW_ENV}"
  secure_file "${NEW_ENV}" && validate_runtime_values "${NEW_ENV}"
}

atomic_replace_runtime_from() {
  local source="$1" status=0
  secure_file "${source}" || return 78
  [[ ! -L "${ENV_FILE}" ]] || return 78
  create_secure_copy "${source}" "${RUNTIME_TEMP_PATH}" || status=$?
  ((status == 0)) && mv -T -- "${RUNTIME_TEMP_PATH}" "${ENV_FILE}" || status=$?
  if ((status != 0)); then
    remove_secure_stage "${RUNTIME_TEMP_PATH}" || status=70
    return "${status}"
  fi
  sync -f "${SECRET_ROOT}"
  secure_file "${ENV_FILE}" && validate_runtime_values "${ENV_FILE}"
}

service_is_healthy() {
  local service="$1" id running health
  id="$(stack ps --all -q "${service}")" || return 1
  [[ "${id}" =~ ^[0-9a-f]{12,64}$ ]] || return 1
  running="$(docker inspect --format '{{.State.Running}}' "${id}")" || return 1
  health="$(docker inspect --format \
    '{{if .Config.Healthcheck}}{{.State.Health.Status}}{{else}}none{{end}}' \
    "${id}")" || return 1
  [[ "${running}" == true && "${health}" == healthy ]]
}

require_live_services() {
  local service
  for service in gateway api worker media-worker; do
    service_is_healthy "${service}" || {
      echo "Required live service is not healthy: ${service}" >&2
      return 69
    }
  done
}

stop_rotation_services() {
  local running
  stack stop --timeout 30 gateway || return 70
  stack stop --timeout 30 api worker media-worker || return 70
  running="$(stack ps --status running -q gateway api worker media-worker)" || return 70
  [[ -z "${running}" ]] || return 70
}

bootstrap_roles() {
  stack run --rm --no-deps -T database-bootstrap
}

recreate_internal_services() {
  stack up -d --no-deps --force-recreate --wait --wait-timeout 300 api
  stack up -d --no-deps --force-recreate --wait --wait-timeout 300 \
    worker media-worker
}

credential_connects() {
  local source="$1" password_key="$2" role="$3" database="$4" password
  password="$(read_env_value_from "${source}" "${password_key}")" || return 78
  printf '%s\n' "${password}" | stack exec -T postgres sh -ceu '
    IFS= read -r PGPASSWORD
    test -n "$PGPASSWORD"; export PGPASSWORD LC_ALL=C
    # Loopback is trusted during image initialization; service DNS crosses the SCRAM boundary.
    exec psql --no-psqlrc --no-password --host=postgres \
      --username="$1" --dbname="$2" --no-align --tuples-only \
      --set=ON_ERROR_STOP=1 --command="SELECT 1"
  ' database-role-probe "${role}" "${database}"
}

verify_credentials_accept() {
  local source="$1" database index
  database="$(read_env_value_from "${source}" POSTGRES_DB)" || return 78
  for index in "${!PASSWORD_KEYS[@]}"; do
    if ! credential_connects "${source}" "${PASSWORD_KEYS[${index}]}" \
      "${ROLE_NAMES[${index}]}" "${database}" >/dev/null; then
      echo "A required database role did not accept its staged credential." >&2
      return 70
    fi
  done
}

verify_old_credentials_rejected() {
  local database index error_file status
  database="$(read_env_value_from "${OLD_ENV}" POSTGRES_DB)" || return 78
  for index in "${!PASSWORD_KEYS[@]}"; do
    credential_connects "${ENV_FILE}" "${PASSWORD_KEYS[${index}]}" \
      "${ROLE_NAMES[${index}]}" "${database}" >/dev/null || return 70
    error_file="$(mktemp -- "${SECRET_ROOT}/.database-role-rejection.XXXXXX")"
    chown 0:0 "${error_file}"; chmod 0600 "${error_file}"
    status=0
    credential_connects "${OLD_ENV}" "${PASSWORD_KEYS[${index}]}" \
      "${ROLE_NAMES[${index}]}" "${database}" \
      >/dev/null 2>"${error_file}" || status=$?
    if ((status == 0)) || ! grep -Fq \
      "password authentication failed for user \"${ROLE_NAMES[${index}]}\"" \
      "${error_file}"; then
      : >"${error_file}"; rm -f -- "${error_file}"
      echo "A retired database credential was not independently rejected." >&2
      return 70
    fi
    : >"${error_file}"; rm -f -- "${error_file}"
    credential_connects "${ENV_FILE}" "${PASSWORD_KEYS[${index}]}" \
      "${ROLE_NAMES[${index}]}" "${database}" >/dev/null || return 70
  done
}

stop_gateway_fail_closed() {
  stack stop --timeout 30 gateway >/dev/null 2>&1 || return 70
}

start_gateway_fail_closed() {
  firewall --prepare >/dev/null || return 69
  if ! stack up -d --no-deps --force-recreate --wait --wait-timeout 300 gateway; then
    if ! stop_gateway_fail_closed; then
      return 70
    fi
    return 70
  fi
  if ! firewall >/dev/null; then
    if ! stop_gateway_fail_closed; then
      return 70
    fi
    return 69
  fi
}

remove_secure_stage() {
  local path="$1"
  [[ -n "${path}" ]] || return 0
  if [[ ! -e "${path}" && ! -L "${path}" ]]; then
    return 0
  fi
  secure_file "${path}" || return 78
  : >"${path}"
  sync -f "${path}"
  rm -- "${path}"
}

cleanup_staging() {
  remove_secure_stage "${RUNTIME_TEMP_PATH}" || return
  remove_secure_stage "${NEW_ENV}" || return
  remove_secure_stage "${OLD_ENV}" || return
  sync -f "${SECRET_ROOT}"
}

rollback_steps() {
  stop_rotation_services || return
  remove_secure_stage "${RUNTIME_TEMP_PATH}" || return
  atomic_replace_runtime_from "${OLD_ENV}" || return
  stack validate || return
  bootstrap_roles || return
  recreate_internal_services || return
  verify_credentials_accept "${OLD_ENV}" || return
  start_gateway_fail_closed || return
  write_journal rolled-back
}

perform_rollback() {
  if rollback_steps; then
    return 0
  fi
  if ! stop_gateway_fail_closed; then
    echo "The gateway could not be closed after rollback failure." >&2
  fi
  echo "Rollback could not prove the old roles and gateway boundary; gateway is closed." >&2
  return 70
}

finish() {
  local status=$?
  trap - EXIT HUP INT TERM
  if [[ "${ROLLBACK_ARMED}" == true ]]; then
    echo "Rotation failed before commit; restoring the staged database roles." >&2
    if perform_rollback; then
      ROLLBACK_ARMED=false
      cleanup_staging || status=70
      printf '{"outcome":"rolled_back","operation_id":"%s"}\n' \
        "${ROTATION_ID}" >&2
    else
      status=70
    fi
  elif ! cleanup_staging; then
    status=70
  fi
  exit "${status}"
}

execute_rotation() {
  prepare_new_rotation
  ROLLBACK_ARMED=true
  write_journal preparing
  stop_rotation_services
  atomic_replace_runtime_from "${NEW_ENV}"
  stack validate
  bootstrap_roles
  recreate_internal_services
  verify_credentials_accept "${ENV_FILE}"
  verify_old_credentials_rejected
  start_gateway_fail_closed
  write_journal committed
  ROLLBACK_ARMED=false
  cleanup_staging
  printf '{"outcome":"rotated","state":"committed","operation_id":"%s"}\n' \
    "${ROTATION_ID}"
}

recover_rotation() {
  load_journal || return 78
  if [[ "${JOURNAL_STATE}" != preparing ]]; then
    if [[ -e "${OLD_ENV_PATH}" || -L "${OLD_ENV_PATH}" \
      || -e "${NEW_ENV_PATH}" || -L "${NEW_ENV_PATH}" \
      || -e "${RUNTIME_TEMP_PATH}" || -L "${RUNTIME_TEMP_PATH}" ]]; then
      OLD_ENV="${OLD_ENV_PATH}"
      NEW_ENV="${NEW_ENV_PATH}"
      cleanup_staging
      printf '{"outcome":"staging_cleaned","state":"%s"}\n' \
        "${JOURNAL_STATE}"
      return 0
    fi
    echo "No interrupted database-role rotation is awaiting recovery." >&2
    return 64
  fi
  stage_paths_for_id
  secure_file "${OLD_ENV}" || {
    echo "The interrupted rotation credential snapshot is unsafe or absent." >&2
    return 78
  }
  ROLLBACK_ARMED=true
  perform_rollback
  ROLLBACK_ARMED=false
  cleanup_staging
  printf '{"outcome":"recovered","operation_id":"%s"}\n' "${ROTATION_ID}"
}

main() {
  local action="${1:-}"
  [[ "$#" == 1 && ( "${action}" == rotate || "${action}" == recover ) ]] || {
    echo "Usage: $0 {rotate|recover}" >&2
    return 64
  }
  acquire_little_orbit_operations_lock wait 300 || {
    echo "Operations lock wait timed out." >&2
    return 75
  }
  require_target
  stack validate
  trap finish EXIT
  trap 'exit 130' HUP INT TERM
  if [[ "${action}" == rotate ]]; then
    require_live_services
    execute_rotation
  else
    recover_rotation
  fi
}

if [[ "${BASH_SOURCE[0]}" == "$0" ]]; then
  main "$@"
fi
