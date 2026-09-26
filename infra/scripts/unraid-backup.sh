#!/usr/bin/env bash
set -euo pipefail

readonly SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
readonly STACK="${SCRIPT_DIR}/unraid-stack.sh"
readonly ENV_FILE="${LITTLE_ORBIT_ENV_FILE:-/mnt/cache/little-orbit-secrets/runtime.env}"
readonly BACKUP_ROOT="${LITTLE_ORBIT_BACKUP_ROOT:-/mnt/user/little-orbit-backups}"
readonly RETENTION_DAYS="${LITTLE_ORBIT_BACKUP_RETENTION_DAYS:-14}"
readonly AGE_BIN="${LITTLE_ORBIT_AGE_BIN:-/mnt/cache/little-orbit-tools/bin/age}"
readonly TIMESTAMP="$(date -u +%Y%m%d-%H%M%S)"
readonly DATABASE_DIR="${BACKUP_ROOT}/postgres"
readonly ATTACHMENT_DIR="${BACKUP_ROOT}/attachments"
readonly MANIFEST_DIR="${BACKUP_ROOT}/manifests"
readonly DATABASE_PATH="${DATABASE_DIR}/little-orbit-${TIMESTAMP}.dump.age"
readonly ATTACHMENT_PATH="${ATTACHMENT_DIR}/little-orbit-attachments-${TIMESTAMP}.tar.age"
readonly PAIR_PATH="${MANIFEST_DIR}/little-orbit-pair-${TIMESTAMP}.json"
readonly WRITER_SERVICES=(api worker media-worker)
writer_ids=()
resume_required=false

stack() {
  bash "${STACK}" "$@"
}

unraid_storage_ready() {
  local cache user
  mountpoint --quiet -- /mnt/cache && mountpoint --quiet -- /mnt/user || return 1
  cache="$(findmnt --noheadings --raw --mountpoint /mnt/cache \
    --output TARGET,SOURCE,FSTYPE)" || return 1
  user="$(findmnt --noheadings --raw --mountpoint /mnt/user \
    --output TARGET,SOURCE,FSTYPE)" || return 1
  [[ "${cache}" == "/mnt/cache /dev/"*" btrfs" ]] || return 1
  [[ "${user}" == "/mnt/user shfs fuse.shfs" ]]
}

require_tools() {
  [[ -x "${AGE_BIN}" ]] || { echo "Pinned age binary is unavailable." >&2; exit 69; }
  command -v jq >/dev/null
  command -v sha256sum >/dev/null
  command -v findmnt >/dev/null
  command -v mountpoint >/dev/null
  unraid_storage_ready || {
    echo "The exact Unraid cache and user-share mounts are unavailable." >&2
    exit 69
  }
  [[ "${BACKUP_ROOT}" == /mnt/user/little-orbit-backups ]] || {
    echo "Backup root must be the dedicated Unraid array share." >&2
    exit 78
  }
}

read_recipient() {
  local value
  value="$(sed -n 's/^BACKUP_AGE_RECIPIENT=//p' "${ENV_FILE}" | tail -n 1)"
  value="${value%\"}"; value="${value#\"}"
  [[ "${value}" =~ ^age1[023456789acdefghjklmnpqrstuvwxyz]{58}$ ]] || {
    echo "The backup age recipient is missing or invalid." >&2
    exit 78
  }
  printf '%s' "${value}"
}

writers_ready() {
  local id running health
  for id in "${writer_ids[@]}"; do
    running="$(docker inspect --format '{{.State.Running}}' "${id}")" || return 1
    [[ "${running}" == true ]] || return 1
    health="$(docker inspect --format \
      '{{if .Config.Healthcheck}}{{.State.Health.Status}}{{else}}none{{end}}' \
      "${id}")" || return 1
    [[ "${health}" == none || "${health}" == healthy ]] || return 1
  done
}

capture_running_writers() {
  local service id running
  for service in "${WRITER_SERVICES[@]}"; do
    id="$(stack ps --all -q "${service}")" || return 1
    [[ "${id}" =~ ^[0-9a-f]{12,64}$ ]] || {
      echo "Expected exactly one ${service} container." >&2
      return 69
    }
    running="$(docker inspect --format '{{.State.Running}}' "${id}")" || return 1
    [[ "${running}" == true ]] || {
      echo "Required mutation service is not running: ${service}" >&2
      return 69
    }
    writer_ids+=("${id}")
  done
  writers_ready || {
    echo "Required mutation services are not ready for a coordinated pause." >&2
    return 69
  }
}

pause_writers() {
  capture_running_writers
  resume_required=true
  docker stop "${writer_ids[@]}" >/dev/null
}

wait_for_writer_readiness() {
  local deadline=$((SECONDS + 300))
  until writers_ready; do
    if ((SECONDS >= deadline)); then
      echo "Mutation services did not become ready within five minutes." >&2
      return 70
    fi
    sleep 5
  done
}

resume_writers() {
  ((${#writer_ids[@]} == ${#WRITER_SERVICES[@]})) || return 70
  docker start "${writer_ids[@]}" >/dev/null || return 70
  wait_for_writer_readiness || return 70
  resume_required=false
}

finish() {
  local status=$?
  trap - EXIT
  if [[ "${resume_required}" == true ]] && ! resume_writers; then
    echo "Backup failed to restore every original mutation service." >&2
    status=70
  fi
  exit "${status}"
}

encrypt_database() {
  local recipient="$1" partial="${DATABASE_PATH}.partial"
  rm -f -- "${partial}"
  stack --profile tools run --rm -T backup-postgres | \
    "${AGE_BIN}" --encrypt --recipient "${recipient}" --output "${partial}"
  [[ "$(stat -c %s "${partial}")" -ge 1024 ]] || return 1
  mv -- "${partial}" "${DATABASE_PATH}"
}

encrypt_attachments() {
  local recipient="$1" partial="${ATTACHMENT_PATH}.partial" stream_script
  stream_script="$(<"${SCRIPT_DIR}/stream-attachment-backup.py")"
  rm -f -- "${partial}"
  stack run --rm -T --no-deps --entrypoint python \
    attachment-init -c "${stream_script}" | \
    "${AGE_BIN}" --encrypt --recipient "${recipient}" --output "${partial}"
  [[ "$(stat -c %s "${partial}")" -ge 512 ]] || return 1
  mv -- "${partial}" "${ATTACHMENT_PATH}"
}

write_sidecars() {
  local db_hash attachment_hash
  db_hash="$(sha256sum "${DATABASE_PATH}" | cut -d' ' -f1)"
  attachment_hash="$(sha256sum "${ATTACHMENT_PATH}" | cut -d' ' -f1)"
  jq -n --arg created_at "$(date -u +%FT%TZ)" --arg file "$(basename "${DATABASE_PATH}")" \
    --arg hash "${db_hash}" --argjson bytes "$(stat -c %s "${DATABASE_PATH}")" \
    '{kind:"little-orbit-postgres",created_at:$created_at,encrypted_file:$file,
      encrypted_bytes:$bytes,encrypted_sha256:$hash,raw_location_rows_included:false,
      device_health_rows_included:false,attributable_quiz_feedback_included:false,
      feedback_operation_rows_included:false,anonymous_review_rows_included:false}' \
    >"${DATABASE_PATH}.json.partial"
  mv -- "${DATABASE_PATH}.json.partial" "${DATABASE_PATH}.json"
  jq -n --arg created_at "$(date -u +%FT%TZ)" --arg file "$(basename "${ATTACHMENT_PATH}")" \
    --arg hash "${attachment_hash}" --argjson bytes "$(stat -c %s "${ATTACHMENT_PATH}")" \
    '{kind:"little-orbit-attachments",created_at:$created_at,encrypted_file:$file,
      encrypted_bytes:$bytes,encrypted_sha256:$hash,mutation_services_paused:true}' \
    >"${ATTACHMENT_PATH}.json.partial"
  mv -- "${ATTACHMENT_PATH}.json.partial" "${ATTACHMENT_PATH}.json"
}

write_pair_manifest() {
  local partial="${PAIR_PATH}.partial"
  jq -n --arg created_at "$(date -u +%FT%TZ)" \
    --arg db "postgres/$(basename "${DATABASE_PATH}")" \
    --arg db_hash "$(sha256sum "${DATABASE_PATH}" | cut -d' ' -f1)" \
    --argjson db_bytes "$(stat -c %s "${DATABASE_PATH}")" \
    --arg attachments "attachments/$(basename "${ATTACHMENT_PATH}")" \
    --arg attachment_hash "$(sha256sum "${ATTACHMENT_PATH}" | cut -d' ' -f1)" \
    --argjson attachment_bytes "$(stat -c %s "${ATTACHMENT_PATH}")" \
    '{schema_version:2,created_at:$created_at,
      database:{path:$db,bytes:$db_bytes,sha256:$db_hash},
      attachments:{path:$attachments,bytes:$attachment_bytes,sha256:$attachment_hash},
      raw_coordinates_included:false,device_health_rows_included:false,
      attributable_quiz_feedback_included:false,feedback_operation_rows_included:false,
      anonymous_review_rows_included:false}' >"${partial}"
  mv -- "${partial}" "${PAIR_PATH}"
}

prune_old_pairs() {
  find "${DATABASE_DIR}" "${ATTACHMENT_DIR}" "${MANIFEST_DIR}" -type f \
    -mtime "+${RETENTION_DAYS}" -name 'little-orbit-*' -delete
}

main() {
  local recipient
  require_tools
  install -d -m 0750 "${DATABASE_DIR}" "${ATTACHMENT_DIR}" "${MANIFEST_DIR}"
  recipient="$(read_recipient)"
  trap finish EXIT
  pause_writers
  encrypt_database "${recipient}"
  encrypt_attachments "${recipient}"
  write_sidecars
  resume_writers
  write_pair_manifest
  prune_old_pairs
  jq -n --arg database "${DATABASE_PATH}" --arg attachments "${ATTACHMENT_PATH}" \
    --arg pair_manifest "${PAIR_PATH}" \
    '{database:$database,attachments:$attachments,pair_manifest:$pair_manifest,
      off_host_copy:false,raw_coordinates_included:false,
      attributable_quiz_feedback_included:false,anonymous_review_rows_included:false}'
}

main "$@"
