#!/usr/bin/env bash
set -euo pipefail

readonly SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
readonly STACK="${SCRIPT_DIR}/unraid-stack.sh"
readonly BACKUP_ROOT="${LITTLE_ORBIT_BACKUP_ROOT:-/mnt/user/little-orbit-backups}"
readonly IDENTITY_PATH="${LITTLE_ORBIT_BACKUP_IDENTITY:-/mnt/cache/little-orbit-secrets/backup-age-identity.txt}"
readonly AGE_BIN="${LITTLE_ORBIT_AGE_BIN:-/mnt/cache/little-orbit-tools/bin/age}"
readonly PAIR_PATH="$(find "${BACKUP_ROOT}/manifests" -maxdepth 1 -type f \
  -name 'little-orbit-pair-*.json' -printf '%T@ %p\n' 2>/dev/null | sort -nr | head -n1 | cut -d' ' -f2-)"
readonly DATABASE_NAME="little_orbit_drill"
readonly DATABASE_USER="drill_owner"
drill_container=""

source "${SCRIPT_DIR}/unraid-operation-lock.sh"

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

cleanup() {
  local container="${drill_container}"
  [[ -n "${container}" ]] || return 0
  [[ "${container}" =~ ^[0-9a-f]{12,64}$ ]] || return 70
  docker rm --force "${container}" >/dev/null || return 70
  if docker inspect "${container}" >/dev/null 2>&1; then
    return 70
  fi
  drill_container=""
}

finish() {
  local status=$?
  trap - EXIT
  if ! cleanup; then
    echo "Restore drill cleanup failed; a plaintext drill database may remain." >&2
    status=70
  fi
  exit "${status}"
}

resolve_entry() {
  local key="$1" relative canonical
  relative="$(jq -er ".${key}.path" "${PAIR_PATH}")"
  canonical="$(realpath -m "${BACKUP_ROOT}/${relative}")"
  [[ "${canonical}" == "${BACKUP_ROOT}"/* ]] || {
    echo "A paired backup escaped the dedicated backup root." >&2
    exit 78
  }
  [[ -f "${canonical}" ]] || { echo "A paired backup is missing." >&2; exit 66; }
  printf '%s' "${canonical}"
}

verify_entry() {
  local key="$1" path="$2" expected_hash expected_bytes
  expected_hash="$(jq -er ".${key}.sha256" "${PAIR_PATH}")"
  expected_bytes="$(jq -er ".${key}.bytes" "${PAIR_PATH}")"
  [[ "$(stat -c %s "${path}")" == "${expected_bytes}" ]] || return 1
  [[ "$(sha256sum "${path}" | cut -d' ' -f1)" == "${expected_hash}" ]]
}

validate_pair() {
  [[ -n "${PAIR_PATH}" && -f "${PAIR_PATH}" ]] || {
    echo "A coordinated backup pair is required." >&2
    exit 66
  }
  jq -e '
    .schema_version == 3 and
    (.retained_table_counts | type == "object" and length > 0 and
      all(to_entries[]; (.key | type == "string") and
        (.value | type == "number" and floor == . and . >= 0))) and
    .raw_coordinates_included == false and
    .device_health_rows_included == false and
    .attributable_quiz_feedback_included == false and
    .feedback_operation_rows_included == false and
    .anonymous_review_rows_included == false
  ' "${PAIR_PATH}" >/dev/null || {
    echo "The coordinated backup pair manifest is invalid." >&2
    exit 78
  }
  [[ -f "${IDENTITY_PATH}" && ! -L "${IDENTITY_PATH}" \
    && "$(stat -c '%u:%g:%a' "${IDENTITY_PATH}")" == 0:0:600 ]] || {
    echo "The age identity must be a root:root mode 0600 regular file." >&2
    exit 66
  }
}

start_drill_database() {
  local shape data_tmpfs health deadline
  drill_container="$(stack --profile tools run -d --rm --no-deps restore-drill-postgres \
    | tr -d '\r')"
  [[ "${drill_container}" =~ ^[0-9a-f]{12,64}$ ]] || {
    echo "The isolated restore database did not return one container id." >&2
    exit 69
  }
  shape="$(docker inspect --format \
    '{{.HostConfig.NetworkMode}}|{{.HostConfig.ReadonlyRootfs}}|{{.Config.User}}' \
    "${drill_container}")"
  data_tmpfs="$(docker inspect --format \
    '{{index .HostConfig.Tmpfs "/var/lib/postgresql/data"}}' "${drill_container}")"
  [[ "${shape}" == "none|true|999:70" \
    && ",${data_tmpfs}," == *",size=4g,"* \
    && ",${data_tmpfs}," == *",mode=0700,"* \
    && ",${data_tmpfs}," == *",uid=999,"* \
    && ",${data_tmpfs}," == *",gid=70,"* ]] || {
    echo "The isolated restore database runtime boundary changed." >&2
    exit 78
  }
  deadline=$((SECONDS + 120))
  while true; do
    health="$(docker inspect --format '{{if .State.Health}}{{.State.Health.Status}}{{else}}missing{{end}}' \
      "${drill_container}")"
    [[ "${health}" == healthy ]] && return 0
    [[ "${health}" != unhealthy && "${health}" != missing ]] || break
    ((SECONDS < deadline)) || break
    sleep 2
  done
  echo "The isolated restore database did not become healthy." >&2
  exit 69
}

restore_database() {
  local backup="$1"
  "${AGE_BIN}" --decrypt --identity "${IDENTITY_PATH}" "${backup}" | \
    docker exec -i "${drill_container}" pg_restore --no-owner --no-acl \
      --exit-on-error --single-transaction --username="${DATABASE_USER}" \
      --dbname="${DATABASE_NAME}"
}

verify_database() {
  local result actual expected
  result="$(docker exec "${drill_container}" psql --username="${DATABASE_USER}" \
    --dbname="${DATABASE_NAME}" --no-psqlrc --no-align --tuples-only \
    --set=ON_ERROR_STOP=1 \
    --command="SELECT CASE WHEN
      to_regclass('public.alembic_version') IS NOT NULL AND
      to_regclass('public.accounts') IS NOT NULL AND
      to_regclass('public.questions') IS NOT NULL AND
      to_regclass('public.question_feedback') IS NOT NULL AND
      to_regclass('public.admin_devices') IS NOT NULL AND
      (SELECT count(*) FROM public.alembic_version) = 1 AND
      (SELECT version_num FROM public.alembic_version) = '0032' AND
      (SELECT count(*) FROM public.location_samples) = 0 AND
      (SELECT count(*) FROM public.together_device_health) = 0 AND
      (SELECT count(*) FROM public.question_feedback) = 0 AND
      (SELECT count(*) FROM public.question_feedback_operations) = 0 AND
      (SELECT count(*) FROM public.anonymous_question_reviews) = 0
      THEN 'ok' ELSE 'invalid' END;" | tr -d '\r')"
  [[ "${result}" == "ok" ]] || { echo "Restored database validation failed." >&2; exit 65; }
  actual="$(docker exec "${drill_container}" psql --username="${DATABASE_USER}" \
    --dbname="${DATABASE_NAME}" --no-psqlrc --no-align --tuples-only \
    --set=ON_ERROR_STOP=1 --command="
      WITH table_counts AS (
        SELECT tablename,
          ((xpath('/row/count/text()', query_to_xml(
            format('SELECT count(*) AS count FROM %I.%I', schemaname, tablename),
            false, true, '')))[1]::text)::bigint AS row_count
        FROM pg_tables WHERE schemaname = 'public'
      )
      SELECT jsonb_object_agg(tablename, row_count ORDER BY tablename)
      FROM table_counts;" | tr -d '\r')"
  actual="$(jq -c -S . <<<"${actual}")"
  expected="$(jq -c -S .retained_table_counts "${PAIR_PATH}")"
  [[ "${actual}" == "${expected}" ]] || {
    echo "Restored retained-table counts do not match the backup snapshot." >&2
    exit 65
  }
}

verify_attachments() {
  local backup="$1" verifier
  verifier="$(<"${SCRIPT_DIR}/verify-attachment-backup.py")"
  "${AGE_BIN}" --decrypt --identity "${IDENTITY_PATH}" "${backup}" | \
    stack --profile tools run --rm -T --no-deps --entrypoint python \
      backup-attachment-verifier -c "${verifier}"
}

main() {
  local database_backup attachment_backup
  acquire_little_orbit_operations_lock wait 300 || {
    echo "Operations lock wait timed out." >&2
    return 75
  }
  [[ -x "${AGE_BIN}" ]]; command -v jq >/dev/null; command -v sha256sum >/dev/null
  command -v findmnt >/dev/null; command -v mountpoint >/dev/null
  command -v flock >/dev/null; command -v realpath >/dev/null; command -v stat >/dev/null
  unraid_storage_ready || {
    echo "The exact Unraid cache and user-share mounts are unavailable." >&2
    exit 69
  }
  [[ "${BACKUP_ROOT}" == /mnt/user/little-orbit-backups \
    && -d "${BACKUP_ROOT}" && ! -L "${BACKUP_ROOT}" \
    && "$(realpath -e "${BACKUP_ROOT}")" == /mnt/user/little-orbit-backups ]] || {
    echo "Backup root must be a real directory on the dedicated array share." >&2
    exit 78
  }
  exec 8>/var/lock/little-orbit-restore-drill.lock
  flock --nonblock 8 || { echo "Another restore drill is active." >&2; exit 69; }
  trap finish EXIT
  validate_pair
  database_backup="$(resolve_entry database)"
  attachment_backup="$(resolve_entry attachments)"
  verify_entry database "${database_backup}"
  verify_entry attachments "${attachment_backup}"
  start_drill_database
  restore_database "${database_backup}"
  verify_database
  verify_attachments "${attachment_backup}"
  cleanup
  jq -n --arg pair_manifest_sha256 "$(sha256sum "${PAIR_PATH}" | cut -d' ' -f1)" \
    '{database_schema:"0032",excluded_private_rows:"verified_empty",
      attachment_manifest:"verified",pair_manifest_sha256:$pair_manifest_sha256}'
}

main "$@"
