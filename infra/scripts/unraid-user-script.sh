#!/usr/bin/env bash
set -euo pipefail

readonly MODE="${1:-}"
readonly SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"

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
  if ! bash "${SCRIPT_DIR}/unraid-stack.sh" stop gateway; then
    echo "Little Orbit gateway could not be stopped after startup verification failed." >&2
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

case "${MODE}" in
  startup)
    wait_for_runtime
    bash "${SCRIPT_DIR}/unraid-firewall.sh"
    bash "${SCRIPT_DIR}/unraid-bootstrap.sh"
    start_stack_fail_closed
    ;;
  pending|backup|test_restore)
    wait_for_runtime
    exec bash "${SCRIPT_DIR}/unraid-operations.sh" "${MODE}"
    ;;
  *)
    echo "Usage: $0 {startup|pending|backup|test_restore}" >&2
    exit 64
    ;;
esac
