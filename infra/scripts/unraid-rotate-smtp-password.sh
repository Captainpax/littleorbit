#!/usr/bin/env bash
set -euo pipefail

if [[ "$-" == *x* ]]; then
  echo "SMTP password rotation refuses shell tracing." >&2
  exit 78
fi

readonly SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
readonly STACK="${SCRIPT_DIR}/unraid-stack.sh"
readonly SECRET_ROOT="/mnt/cache/little-orbit-secrets"
readonly ENV_FILE="${SECRET_ROOT}/runtime.env"
readonly JOURNAL_FILE="${SECRET_ROOT}/smtp-password-rotation.state"
readonly OLD_ENV_PATH="${SECRET_ROOT}/.smtp-password-rotation.old.env"
readonly NEW_ENV_PATH="${SECRET_ROOT}/.smtp-password-rotation.new.env"
readonly RUNTIME_TEMP_PATH="${SECRET_ROOT}/.smtp-password-rotation.runtime.env"

ACTION=""
INPUT_MODE=""
INPUT_PATH=""
INPUT_STAGE=""
NEW_PASSWORD=""
ROTATION_ID=""
JOURNAL_STATE="absent"
ROTATION_ACTIVE=false
ROLLBACK_ARMED=false

source "${SCRIPT_DIR}/unraid-operation-lock.sh"

stack() {
  bash "${STACK}" "$@"
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

validate_smtp_layout() {
  local path="$1" host port starttls
  host="$(read_env_value_from "${path}" SMTP_HOST)" || return 78
  port="$(read_env_value_from "${path}" SMTP_PORT)" || return 78
  starttls="$(read_env_value_from "${path}" SMTP_STARTTLS)" || return 78
  [[ "${host}" == smtp.gmail.com && "${port}" == 587 \
    && "${starttls,,}" == true ]] || return 78
  read_env_value_from "${path}" SMTP_USERNAME >/dev/null || return 78
  read_env_value_from "${path}" SMTP_PASSWORD >/dev/null || return 78
}

require_target() {
  [[ "$(id -u)" == 0 ]] || {
    echo "SMTP password rotation must run as root." >&2
    return 77
  }
  local command
  for command in awk cmp flock head mktemp openssl realpath stat sync; do
    command -v "${command}" >/dev/null || return 69
  done
  [[ -d "${SECRET_ROOT}" && ! -L "${SECRET_ROOT}" \
    && "$(realpath -e "${SECRET_ROOT}")" == "${SECRET_ROOT}" \
    && "$(stat -c '%F:%u:%g:%a' "${SECRET_ROOT}")" == \
    "directory:0:0:700" ]] || {
    echo "The fixed Little Orbit secrets directory is unsafe." >&2
    return 78
  }
  secure_file "${ENV_FILE}" || {
    echo "runtime.env must be a root-owned mode-0600 single-link file." >&2
    return 78
  }
  [[ "$(realpath -e "${ENV_FILE}")" == "${ENV_FILE}" ]] || return 78
  validate_smtp_layout "${ENV_FILE}" || {
    echo "runtime.env must contain one complete Gmail SMTP definition." >&2
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

stage_exists() { [[ -e "$1" || -L "$1" ]]; }

stage_has_content() { [[ -s "$1" ]]; }

transient_staging_is_absent() {
  ! stage_exists "${RUNTIME_TEMP_PATH}" && ! stage_exists "${NEW_ENV_PATH}"
}

all_staging_is_absent() {
  transient_staging_is_absent && ! stage_exists "${OLD_ENV_PATH}"
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
  [[ "${lines[2]}" =~ ^state=(preparing|awaiting-test|committed|rolled-back)$ ]] \
    || return 78
  JOURNAL_STATE="${BASH_REMATCH[1]}"
}

write_journal() {
  local state="$1" temporary status=0
  [[ "${ROTATION_ID}" =~ ^[0-9a-f]{32}$ \
    && "${state}" =~ ^(preparing|awaiting-test|committed|rolled-back)$ ]] \
    || return 64
  [[ ! -L "${JOURNAL_FILE}" ]] || return 78
  temporary="$(mktemp -- "${SECRET_ROOT}/.smtp-password-state.XXXXXX")"
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

read_password_file() {
  local path="$1" size extra=""
  size="$(stat -c '%s' "${path}")" || return 69
  [[ "${size}" == 16 || "${size}" == 17 ]] || return 65
  NEW_PASSWORD=""
  exec 5<"${path}"
  IFS= read -r NEW_PASSWORD <&5 || [[ -n "${NEW_PASSWORD}" ]]
  if IFS= read -r extra <&5 || [[ -n "${extra}" ]]; then
    exec 5<&-
    return 65
  fi
  exec 5<&-
  [[ "${NEW_PASSWORD}" =~ ^[A-Za-z0-9]{16}$ ]]
}

capture_stdin() {
  [[ ! -t 0 ]] || {
    echo "Refusing to read an SMTP password from an interactive terminal." >&2
    return 64
  }
  INPUT_STAGE="$(mktemp -- "${SECRET_ROOT}/.smtp-password-input.XXXXXX")"
  chown 0:0 "${INPUT_STAGE}"; chmod 0600 "${INPUT_STAGE}"
  secure_file "${INPUT_STAGE}" || return 78
  head -c 18 >"${INPUT_STAGE}" || return 65
  sync -f "${INPUT_STAGE}"
  read_password_file "${INPUT_STAGE}"
}

load_new_password() {
  local mode="$1" path="${2:-}"
  if [[ "${mode}" == file ]]; then
    secure_file "${path}" || {
      echo "The password source must be a root-owned mode-0600 single-link file." >&2
      return 78
    }
    [[ "$(realpath -e "${path}")" != "${ENV_FILE}" ]] || return 78
    read_password_file "${path}" || {
      echo "The Gmail app password must be one 16-character alphanumeric line." >&2
      return 65
    }
  else
    local status=0
    capture_stdin || status=$?
    if ((status != 0)); then
      echo "Standard input must contain one 16-character Gmail app password line." >&2
      return "${status}"
    fi
  fi
}

render_rotated_env() {
  local source="$1" destination="$2" line key replaced=0
  [[ -f "${source}" && ! -L "${source}" \
    && -f "${destination}" && ! -L "${destination}" ]] || return 78
  : >"${destination}"
  while IFS= read -r line || [[ -n "${line}" ]]; do
    line="${line%$'\r'}"
    key="$(env_definition_key "${line}")"
    if [[ "${key}" == SMTP_PASSWORD ]]; then
      ((replaced += 1))
      ((replaced == 1)) || return 78
      printf 'SMTP_PASSWORD=%s\n' "${NEW_PASSWORD}" >>"${destination}"
    else
      printf '%s\n' "${line}" >>"${destination}"
    fi
  done <"${source}"
  ((replaced == 1))
}

prepare_new_rotation() {
  local mode="$1" path="${2:-}" old_password
  load_journal || {
    echo "The SMTP rotation journal is invalid." >&2
    return 78
  }
  [[ "${JOURNAL_STATE}" != preparing \
    && "${JOURNAL_STATE}" != awaiting-test ]] || {
    echo "The prior SMTP rotation must be committed or rolled back first." >&2
    return 75
  }
  if [[ -e "${OLD_ENV_PATH}" || -L "${OLD_ENV_PATH}" \
    || -e "${NEW_ENV_PATH}" || -L "${NEW_ENV_PATH}" \
    || -e "${RUNTIME_TEMP_PATH}" || -L "${RUNTIME_TEMP_PATH}" ]]; then
    echo "Prior SMTP credential staging requires reviewed cleanup." >&2
    return 78
  fi
  load_new_password "${mode}" "${path}"
  old_password="$(read_env_value_from "${ENV_FILE}" SMTP_PASSWORD)" || return 78
  [[ "${NEW_PASSWORD}" != "${old_password}" ]] || {
    echo "The replacement SMTP password is unchanged." >&2
    return 65
  }
  ROTATION_ID="$(openssl rand -hex 16)"
  [[ "${ROTATION_ID}" =~ ^[0-9a-f]{32}$ ]] || return 69
  ROTATION_ACTIVE=true
  if ! create_secure_copy "${ENV_FILE}" "${OLD_ENV_PATH}"; then
    remove_secure_stage "${OLD_ENV_PATH}" >/dev/null 2>&1 || true
    return 73
  fi
  ROLLBACK_ARMED=true
  write_journal preparing
  create_secure_empty "${NEW_ENV_PATH}"
  render_rotated_env "${OLD_ENV_PATH}" "${NEW_ENV_PATH}"
  chown 0:0 "${NEW_ENV_PATH}"; chmod 0600 "${NEW_ENV_PATH}"
  sync -f "${NEW_ENV_PATH}"
  secure_file "${NEW_ENV_PATH}" && validate_smtp_layout "${NEW_ENV_PATH}"
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
  secure_file "${ENV_FILE}" && validate_smtp_layout "${ENV_FILE}"
}

service_is_healthy() {
  local id running health
  id="$(stack ps --all -q worker)" || return 1
  [[ "${id}" =~ ^[0-9a-f]{12,64}$ ]] || return 1
  running="$(docker inspect --format '{{.State.Running}}' "${id}")" || return 1
  health="$(docker inspect --format \
    '{{if .Config.Healthcheck}}{{.State.Health.Status}}{{else}}none{{end}}' \
    "${id}")" || return 1
  [[ "${running}" == true && "${health}" == healthy ]]
}

require_live_worker() {
  service_is_healthy || {
    echo "The production worker must be healthy before SMTP rotation." >&2
    return 69
  }
}

stop_worker_fail_closed() {
  local running
  stack stop --timeout 30 worker || return 70
  running="$(stack ps --status running -q worker)" || return 70
  [[ -z "${running}" ]] || return 70
}

recreate_worker() {
  stack up -d --no-deps --force-recreate --wait --wait-timeout 300 worker \
    || return 70
  service_is_healthy || return 70
}

cleanup_transient() {
  remove_secure_stage "${RUNTIME_TEMP_PATH}" || return
  remove_secure_stage "${NEW_ENV_PATH}" || return
  sync -f "${SECRET_ROOT}"
}

cleanup_all_staging() {
  cleanup_transient || return
  remove_secure_stage "${OLD_ENV_PATH}" || return
  sync -f "${SECRET_ROOT}"
}

prove_rolled_back_runtime() {
  secure_file "${ENV_FILE}" && validate_smtp_layout "${ENV_FILE}" || return 78
  if ! stage_exists "${OLD_ENV_PATH}"; then
    transient_staging_is_absent || return 78
    return 0
  fi
  secure_file "${OLD_ENV_PATH}" || return 78
  if ! stage_has_content "${OLD_ENV_PATH}"; then
    transient_staging_is_absent || return 78
    return 0
  fi
  validate_smtp_layout "${OLD_ENV_PATH}" || return 78
  cmp -s -- "${OLD_ENV_PATH}" "${ENV_FILE}" || return 78
}

recover_rolled_back_staging() {
  prove_rolled_back_runtime || return
  cleanup_all_staging || return
  all_staging_is_absent || return 78
}

rollback_steps() {
  stop_worker_fail_closed || return
  remove_secure_stage "${RUNTIME_TEMP_PATH}" || return
  atomic_replace_runtime_from "${OLD_ENV_PATH}" || return
  stack validate || return
  recreate_worker || return
  write_journal rolled-back
}

perform_rollback() {
  if rollback_steps; then
    return 0
  fi
  if stop_worker_fail_closed >/dev/null 2>&1; then
    echo "Rollback could not prove the old SMTP worker; the worker is stopped." >&2
  else
    echo "Rollback and the final worker stop could not be verified." >&2
  fi
  return 70
}

cleanup_input() {
  if [[ -n "${INPUT_STAGE}" ]]; then
    remove_secure_stage "${INPUT_STAGE}" || return
    INPUT_STAGE=""
  fi
  NEW_PASSWORD=""
  unset NEW_PASSWORD
}

finish() {
  local status=$?
  trap - EXIT HUP INT TERM
  if [[ "${ROLLBACK_ARMED}" == true ]]; then
    echo "SMTP rotation failed before operator confirmation; restoring the old worker." >&2
    if perform_rollback; then
      ROLLBACK_ARMED=false
      cleanup_all_staging || status=70
      printf '{"outcome":"rolled_back","operation_id":"%s"}\n' \
        "${ROTATION_ID}" >&2
    else
      status=70
      cleanup_transient || status=70
    fi
  elif [[ "${ROTATION_ACTIVE}" == true ]]; then
    cleanup_transient || status=70
  fi
  cleanup_input || status=70
  exit "${status}"
}

execute_rotation() {
  local mode="$1" path="${2:-}"
  prepare_new_rotation "${mode}" "${path}"
  stop_worker_fail_closed
  atomic_replace_runtime_from "${NEW_ENV_PATH}"
  stack validate
  recreate_worker
  write_journal awaiting-test
  ROLLBACK_ARMED=false
  cleanup_transient
  printf '{"outcome":"awaiting_test","operation_id":"%s"}\n' "${ROTATION_ID}"
}

commit_rotation() {
  load_journal || return 78
  if [[ "${JOURNAL_STATE}" == committed && -e "${OLD_ENV_PATH}" ]]; then
    secure_file "${OLD_ENV_PATH}" || return 78
    remove_secure_stage "${OLD_ENV_PATH}"
    printf '{"outcome":"staging_cleaned","operation_id":"%s"}\n' "${ROTATION_ID}"
    return 0
  fi
  [[ "${JOURNAL_STATE}" == awaiting-test ]] || {
    echo "No tested SMTP rotation is awaiting commit." >&2
    return 64
  }
  secure_file "${OLD_ENV_PATH}" || return 78
  require_live_worker
  write_journal committed
  remove_secure_stage "${OLD_ENV_PATH}"
  sync -f "${SECRET_ROOT}"
  printf '{"outcome":"committed","operation_id":"%s"}\n' "${ROTATION_ID}"
}

rollback_rotation() {
  local status=0
  load_journal || return 78
  if [[ "${JOURNAL_STATE}" == rolled-back ]]; then
    recover_rolled_back_staging || status=$?
    if ((status != 0)); then
      echo "Rolled-back SMTP staging is inconsistent or unsafe." >&2
      return "${status}"
    fi
    printf '{"outcome":"rolled_back","operation_id":"%s"}\n' "${ROTATION_ID}"
    return 0
  fi
  [[ "${JOURNAL_STATE}" == preparing \
    || "${JOURNAL_STATE}" == awaiting-test ]] || {
    echo "No SMTP rotation is available for rollback." >&2
    return 64
  }
  secure_file "${OLD_ENV_PATH}" || {
    echo "The old SMTP environment snapshot is unsafe or absent." >&2
    return 78
  }
  ROTATION_ACTIVE=true
  ROLLBACK_ARMED=true
  perform_rollback
  ROLLBACK_ARMED=false
  cleanup_all_staging
  printf '{"outcome":"rolled_back","operation_id":"%s"}\n' "${ROTATION_ID}"
}

parse_cli() {
  ACTION="${1:-}"
  INPUT_MODE=""
  INPUT_PATH=""
  case "${ACTION}" in
    rotate)
      if [[ "$#" == 3 && "$2" == --password-file && -n "$3" ]]; then
        INPUT_MODE=file; INPUT_PATH="$3"
      elif [[ "$#" == 2 && "$2" == --stdin ]]; then
        INPUT_MODE=stdin
      else
        return 64
      fi
      ;;
    commit|rollback) [[ "$#" == 1 ]] || return 64 ;;
    *) return 64 ;;
  esac
}

main() {
  parse_cli "$@" || {
    echo "Usage: $0 {rotate --password-file PATH|rotate --stdin|commit|rollback}" >&2
    return 64
  }
  acquire_little_orbit_operations_lock wait 300 || {
    echo "Operations lock wait timed out." >&2
    return 75
  }
  fix_little_orbit_local_docker_endpoint || {
    echo "The local Unraid Docker socket is unavailable or unsafe." >&2
    return 69
  }
  require_target
  trap finish EXIT
  trap 'exit 130' HUP INT TERM
  case "${ACTION}" in
    rotate)
      stack validate
      require_live_worker
      execute_rotation "${INPUT_MODE}" "${INPUT_PATH}"
      ;;
    commit)
      stack validate
      commit_rotation
      ;;
    rollback) rollback_rotation ;;
  esac
}

if [[ "${BASH_SOURCE[0]}" == "$0" ]]; then
  main "$@"
fi
