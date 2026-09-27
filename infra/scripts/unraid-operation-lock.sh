#!/usr/bin/env bash

# Shared by the dispatcher and every stateful leaf command. The inherited file
# descriptor lets a dispatcher call a leaf without deadlocking itself, while a
# direct leaf invocation still participates in the same host-wide mutex.
readonly LITTLE_ORBIT_OPERATIONS_LOCK_PATH="/var/lock/little-orbit-operations.lock"
readonly LITTLE_ORBIT_MIGRATION_HOLDER_PATH="/var/lock/little-orbit-migration-holder"
readonly LITTLE_ORBIT_MIGRATION_GUARD_PATH="/var/lock/little-orbit-migration-holder.lock"

canonical_operations_lock_path() {
  readlink -m -- "${LITTLE_ORBIT_OPERATIONS_LOCK_PATH}"
}

validate_operations_lock_fd() {
  local descriptor="$1" target expected
  target="$(readlink -f "/proc/$$/fd/${descriptor}")" || return 69
  expected="$(canonical_operations_lock_path)" || return 69
  [[ "${target}" == "${expected}" ]] || {
    echo "The Little Orbit operations lock descriptor is invalid." >&2
    return 78
  }
  [[ "$(stat -Lc '%F:%h' "/proc/$$/fd/${descriptor}")" == "regular empty file:1" ]] || {
    echo "The Little Orbit operations lock inode is unsafe." >&2
    return 78
  }
}

acquire_little_orbit_operations_lock() {
  local behavior="$1" wait_seconds="${2:-300}" inherited
  install -d -m 0755 "$(dirname "${LITTLE_ORBIT_OPERATIONS_LOCK_PATH}")"
  [[ ! -L "${LITTLE_ORBIT_OPERATIONS_LOCK_PATH}" ]] || {
    echo "The Little Orbit operations lock cannot be a symbolic link." >&2
    return 78
  }

  inherited="${LITTLE_ORBIT_OPERATIONS_LOCK_FD:-}"
  if [[ "${inherited}" == 9 && -e /proc/$$/fd/9 ]]; then
    validate_operations_lock_fd 9 || return
    validate_migration_guard_fd 7 || return
    flock --nonblock 9 || {
      echo "The inherited Little Orbit operations lock is not held." >&2
      return 75
    }
    return 0
  fi

  acquire_little_orbit_normal_guard "${behavior}" "${wait_seconds}" || return
  exec 9<>"${LITTLE_ORBIT_OPERATIONS_LOCK_PATH}"
  validate_operations_lock_fd 9 || return
  case "${behavior}" in
    nonblocking) flock --nonblock 9 || return 75 ;;
    wait) flock --wait "${wait_seconds}" 9 || return 75 ;;
    *) echo "Unknown operations-lock behavior." >&2; return 64 ;;
  esac
  export LITTLE_ORBIT_OPERATIONS_LOCK_FD=9
}

acquire_little_orbit_migration_shared_lock() {
  install -d -m 0755 "$(dirname "${LITTLE_ORBIT_OPERATIONS_LOCK_PATH}")"
  [[ ! -L "${LITTLE_ORBIT_OPERATIONS_LOCK_PATH}" ]] || return 78
  exec 9<>"${LITTLE_ORBIT_OPERATIONS_LOCK_PATH}"
  validate_operations_lock_fd 9 || return
  flock --exclusive --nonblock 9 || return 75
  flock --shared 9 || return 75
  export LITTLE_ORBIT_OPERATIONS_LOCK_FD=9
}

validate_migration_guard_fd() {
  local descriptor="$1" target expected
  target="$(readlink -f "/proc/$$/fd/${descriptor}")" || return 69
  expected="$(readlink -m -- "${LITTLE_ORBIT_MIGRATION_GUARD_PATH}")" || return 69
  [[ "${target}" == "${expected}" ]] || return 78
  [[ "$(stat -Lc '%F:%h' "/proc/$$/fd/${descriptor}")" == \
    "regular empty file:1" ]] || return 78
}

acquire_little_orbit_normal_guard() {
  local behavior="$1" wait_seconds="$2"
  [[ ! -L "${LITTLE_ORBIT_MIGRATION_GUARD_PATH}" ]] || return 78
  exec 7<>"${LITTLE_ORBIT_MIGRATION_GUARD_PATH}"
  validate_migration_guard_fd 7 || return
  case "${behavior}" in
    nonblocking) flock --shared --nonblock 7 || return 75 ;;
    wait) flock --shared --wait "${wait_seconds}" 7 || return 75 ;;
    *) return 64 ;;
  esac
}

acquire_little_orbit_migration_holder_guard() {
  [[ ! -L "${LITTLE_ORBIT_MIGRATION_GUARD_PATH}" ]] || return 78
  exec 7<>"${LITTLE_ORBIT_MIGRATION_GUARD_PATH}"
  validate_migration_guard_fd 7 || return
  flock --nonblock 7 || return 75
}

write_little_orbit_migration_holder() {
  local token="$1" record="$$:${token}"
  [[ "${token}" =~ ^[0-9a-f]{64}$ ]] || return 64
  if [[ -e "${LITTLE_ORBIT_MIGRATION_HOLDER_PATH}" \
    || -L "${LITTLE_ORBIT_MIGRATION_HOLDER_PATH}" ]]; then
    [[ ! -L "${LITTLE_ORBIT_MIGRATION_HOLDER_PATH}" \
      && "$(stat -c '%F:%u:%g:%a:%h' "${LITTLE_ORBIT_MIGRATION_HOLDER_PATH}")" == \
      "regular file:0:0:600:1" ]] || return 78
    rm -f -- "${LITTLE_ORBIT_MIGRATION_HOLDER_PATH}"
  fi
  (umask 077; set -o noclobber; printf '%s\n' "${record}" \
    >"${LITTLE_ORBIT_MIGRATION_HOLDER_PATH}") || return 73
  [[ "$(stat -c '%F:%u:%g:%a:%h' "${LITTLE_ORBIT_MIGRATION_HOLDER_PATH}")" == \
    "regular file:0:0:600:1" ]] || return 78
}

remove_little_orbit_migration_holder() {
  local token="$1"
  [[ -f "${LITTLE_ORBIT_MIGRATION_HOLDER_PATH}" \
    && ! -L "${LITTLE_ORBIT_MIGRATION_HOLDER_PATH}" ]] || return 0
  [[ "$(<"${LITTLE_ORBIT_MIGRATION_HOLDER_PATH}")" == "$$:${token}" ]] || return 0
  rm -f -- "${LITTLE_ORBIT_MIGRATION_HOLDER_PATH}"
}

authorize_little_orbit_migration_holder() {
  local token="${LITTLE_ORBIT_MIGRATION_LOCK_TOKEN:-}" record pid stored extra
  local holder_target expected holder_inode path_inode guard_target guard_expected
  [[ "${token}" =~ ^[0-9a-f]{64}$ ]] || return 78
  [[ -f "${LITTLE_ORBIT_MIGRATION_HOLDER_PATH}" \
    && ! -L "${LITTLE_ORBIT_MIGRATION_HOLDER_PATH}" \
    && "$(stat -c '%F:%u:%g:%a:%h' "${LITTLE_ORBIT_MIGRATION_HOLDER_PATH}")" == \
    "regular file:0:0:600:1" ]] || return 78
  record="$(<"${LITTLE_ORBIT_MIGRATION_HOLDER_PATH}")"
  IFS=: read -r pid stored extra <<<"${record}"
  [[ "${pid}" =~ ^[1-9][0-9]*$ && "${stored}" == "${token}" && -z "${extra}" ]] || return 78
  kill -0 "${pid}" 2>/dev/null || return 75
  [[ -e "/proc/${pid}/fd/7" && -e "/proc/${pid}/fd/9" ]] || return 75
  guard_target="$(readlink -f "/proc/${pid}/fd/7")" || return 75
  guard_expected="$(readlink -m -- "${LITTLE_ORBIT_MIGRATION_GUARD_PATH}")" || return 69
  [[ "${guard_target}" == "${guard_expected}" ]] || return 78
  [[ "$(stat -Lc '%d:%i:%F:%h' "/proc/${pid}/fd/7")" == \
    "$(stat -Lc '%d:%i:%F:%h' "${LITTLE_ORBIT_MIGRATION_GUARD_PATH}")" \
    && "$(stat -Lc '%F:%h' "/proc/${pid}/fd/7")" == \
    "regular empty file:1" ]] || return 78
  exec 6<>"${LITTLE_ORBIT_MIGRATION_GUARD_PATH}"
  if flock --nonblock 6; then
    flock --unlock 6
    exec 6>&-
    return 75
  fi
  exec 6>&-
  holder_target="$(readlink -f "/proc/${pid}/fd/9")" || return 75
  expected="$(canonical_operations_lock_path)" || return 69
  [[ "${holder_target}" == "${expected}" ]] || return 78
  holder_inode="$(stat -Lc '%d:%i:%F:%h' "/proc/${pid}/fd/9")" || return 75
  path_inode="$(stat -Lc '%d:%i:%F:%h' "${LITTLE_ORBIT_OPERATIONS_LOCK_PATH}")" || return 75
  [[ "${holder_inode}" == "${path_inode}" \
    && "${holder_inode}" == *":regular empty file:1" ]] || return 78
  exec 8<>"${LITTLE_ORBIT_OPERATIONS_LOCK_PATH}"
  if flock --nonblock 8; then
    flock --unlock 8
    exec 8>&-
    return 75
  fi
  exec 8>&-
  exec 9<>"${LITTLE_ORBIT_OPERATIONS_LOCK_PATH}"
  validate_operations_lock_fd 9 || return
  flock --shared --nonblock 9 || return 75
  kill -0 "${pid}" 2>/dev/null || return 75
  [[ "$(<"${LITTLE_ORBIT_MIGRATION_HOLDER_PATH}")" == "${record}" ]] || return 75
  export LITTLE_ORBIT_OPERATIONS_LOCK_FD=9
}

acquire_or_authorize_little_orbit_operations_lock() {
  local behavior="$1" wait_seconds="${2:-300}"
  if [[ -n "${LITTLE_ORBIT_MIGRATION_LOCK_TOKEN:-}" ]]; then
    authorize_little_orbit_migration_holder || {
      echo "The migration lock-holder capability is invalid." >&2
      return 75
    }
    unset LITTLE_ORBIT_MIGRATION_LOCK_TOKEN
    return 0
  fi
  acquire_little_orbit_operations_lock "${behavior}" "${wait_seconds}"
}

hold_little_orbit_migration_lock() {
  local token="$1" value status=0
  acquire_little_orbit_migration_holder_guard || return
  acquire_little_orbit_migration_shared_lock || return
  write_little_orbit_migration_holder "${token}" || return
  trap "remove_little_orbit_migration_holder '${token}'" EXIT
  printf 'little-orbit-migration-locked\n'
  while IFS= read -r value; do
    value="${value%$'\r'}"
    [[ "${value}" == ping ]] || { status=76; break; }
    printf 'little-orbit-migration-alive\n'
  done
  return "${status}"
}

run_little_orbit_migration_command() {
  local token="$1"
  shift
  [[ "$#" -gt 0 ]] || return 64
  export LITTLE_ORBIT_MIGRATION_LOCK_TOKEN="${token}"
  acquire_or_authorize_little_orbit_operations_lock nonblocking || return
  fix_little_orbit_local_docker_endpoint || return
  exec "$@"
}

run_little_orbit_exclusive_command() {
  local wait_seconds="$1"
  shift
  [[ "${wait_seconds}" =~ ^[1-9][0-9]*$ && "$#" -gt 0 ]] || return 64
  acquire_little_orbit_operations_lock wait "${wait_seconds}" || return
  fix_little_orbit_local_docker_endpoint || return
  exec "$@"
}

fix_little_orbit_local_docker_endpoint() {
  local name
  [[ -S /var/run/docker.sock && ! -L /var/run/docker.sock ]] || return 69
  while IFS= read -r name; do
    case "${name}" in
      DOCKER_*|COMPOSE_*) unset "${name}" ;;
    esac
  done < <(compgen -e)
  export DOCKER_HOST=unix:///var/run/docker.sock
}

if [[ "${BASH_SOURCE[0]}" == "$0" ]]; then
  action="${1:-}"
  if [[ "$#" -gt 0 ]]; then
    shift
  fi
  case "${action}" in
    hold-migration)
      [[ "$#" == 1 ]] || exit 64
      hold_little_orbit_migration_lock "$1"
      ;;
    run-migration)
      [[ "$#" -ge 2 ]] || exit 64
      token="$1"
      shift
      run_little_orbit_migration_command "${token}" "$@"
      ;;
    run-exclusive)
      [[ "$#" -ge 2 ]] || exit 64
      wait_seconds="$1"
      shift
      run_little_orbit_exclusive_command "${wait_seconds}" "$@"
      ;;
    *)
      echo "Usage: $0 {hold-migration TOKEN|run-migration TOKEN COMMAND...|run-exclusive SECONDS COMMAND...}" >&2
      exit 64
      ;;
  esac
fi
