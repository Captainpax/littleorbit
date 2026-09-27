#!/usr/bin/env bash
set -euo pipefail

readonly MODE="${1:-}"
readonly SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"

source "${SCRIPT_DIR}/unraid-timezone.sh"
source "${SCRIPT_DIR}/unraid-operation-lock.sh"

runtime_mounts_ready() {
  local cache user
  mountpoint --quiet -- /mnt/cache && mountpoint --quiet -- /mnt/user || return 1
  cache="$(findmnt --noheadings --raw --mountpoint /mnt/cache \
    --output TARGET,SOURCE,FSTYPE)" || return 1
  user="$(findmnt --noheadings --raw --mountpoint /mnt/user \
    --output TARGET,SOURCE,FSTYPE)" || return 1
  [[ "${cache}" == "/mnt/cache /dev/"*" btrfs" ]] || return 1
  [[ "${user}" == "/mnt/user shfs fuse.shfs" ]]
}

wait_for_runtime() {
  local deadline=$((SECONDS + 300))
  command -v findmnt >/dev/null; command -v mountpoint >/dev/null
  until runtime_mounts_ready && docker info >/dev/null 2>&1; do
    if ((SECONDS >= deadline)); then
      echo "The exact Unraid mounts or Docker did not become ready within five minutes." >&2
      return 69
    fi
    sleep 5
  done
}

stop_gateway_after_failed_startup() {
  local -a gateway_ids=()
  if ! docker info >/dev/null 2>&1; then
    echo "Docker is unavailable while closing the Little Orbit gateway." >&2
    return 69
  fi
  mapfile -t gateway_ids < <(docker ps --quiet \
    --filter label=com.docker.compose.project=little-orbit \
    --filter label=com.docker.compose.service=gateway)
  if ((${#gateway_ids[@]} > 0)) && ! docker stop "${gateway_ids[@]}" >/dev/null; then
    echo "Little Orbit gateway could not be stopped after startup verification failed." >&2
    return 70
  fi
  if docker ps --quiet \
    --filter label=com.docker.compose.project=little-orbit \
    --filter label=com.docker.compose.service=gateway | grep -q .; then
    echo "Little Orbit gateway remains active after fail-closed cleanup." >&2
    return 70
  fi
}

start_stack_fail_closed() {
  if ! bash "${SCRIPT_DIR}/unraid-stack.sh" up -d --wait --wait-timeout 600; then
    stop_gateway_after_failed_startup
    return 70
  fi
  if ! bash "${SCRIPT_DIR}/unraid-firewall.sh"; then
    stop_gateway_after_failed_startup
    return 69
  fi
}

run_startup() {
  local status
  acquire_little_orbit_operations_lock wait 300 || {
    echo "Operations lock wait timed out." >&2
    return 75
  }
  wait_for_runtime || {
    status=$?
    stop_gateway_after_failed_startup || return 70
    return "${status}"
  }
  bash "${SCRIPT_DIR}/unraid-firewall.sh" --prepare || {
    status=$?
    stop_gateway_after_failed_startup || return 70
    return "${status}"
  }
  bash "${SCRIPT_DIR}/unraid-bootstrap.sh" || {
    status=$?
    stop_gateway_after_failed_startup || return 70
    return "${status}"
  }
  start_stack_fail_closed
}

case "${MODE}" in
  startup)
    run_startup
    ;;
  pending)
    wait_for_runtime
    exec bash "${SCRIPT_DIR}/unraid-operations.sh" "${MODE}"
    ;;
  backup|test_restore)
    require_unraid_pacific_timezone
    wait_for_runtime
    exec bash "${SCRIPT_DIR}/unraid-operations.sh" "${MODE}"
    ;;
  *)
    echo "Usage: $0 {startup|pending|backup|test_restore}" >&2
    exit 64
    ;;
esac
