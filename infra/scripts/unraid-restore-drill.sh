#!/usr/bin/env bash
set -euo pipefail

readonly SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
readonly STACK="${SCRIPT_DIR}/unraid-stack.sh"
readonly BACKUP_ROOT="${LITTLE_ORBIT_BACKUP_ROOT:-/mnt/user/little-orbit-backups}"
readonly IDENTITY_PATH="${LITTLE_ORBIT_BACKUP_IDENTITY:-/mnt/cache/little-orbit-secrets/backup-age-identity.txt}"
readonly AGE_BIN="${LITTLE_ORBIT_AGE_BIN:-/mnt/cache/little-orbit-tools/bin/age}"
readonly PAIR_PATH="$(find "${BACKUP_ROOT}/manifests" -maxdepth 1 -type f \
  -name 'little-orbit-pair-*.json' -printf '%T@ %p\n' 2>/dev/null | sort -nr | head -n1 | cut -d' ' -f2-)"
readonly DATABASE_NAME="little_orbit_drill_$(date -u +%Y%m%d%H%M%S)"
created_database=false
database_user=""

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

valid_drill_name() {
  [[ "$1" =~ ^little_orbit_drill_[0-9]{14}$ ]]
}

drop_drill_database() {
  local name="$1" force="${2:-false}" arguments=()
  valid_drill_name "${name}" || return 78
  [[ -n "${database_user}" ]] || return 70
  [[ "${force}" == true ]] && arguments+=(--force)
  stack exec -T postgres dropdb --username="${database_user}" \
    --maintenance-db=postgres --if-exists "${arguments[@]}" "${name}" >/dev/null
}

cleanup() {
  if [[ "${created_database}" == true ]]; then
    drop_drill_database "${DATABASE_NAME}" true || return 70
    created_database=false
  fi
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

remove_stale_drill_databases() {
  local listing name active
  listing="$(stack exec -T postgres psql --username="${database_user}" \
    --dbname=postgres --no-psqlrc --no-align --tuples-only --field-separator='|' \
    --set=ON_ERROR_STOP=1 --command="SELECT d.datname,
      EXISTS (SELECT 1 FROM pg_stat_activity a WHERE a.datname = d.datname)
      FROM pg_database d
      WHERE d.datname ~ '^little_orbit_drill_[0-9]{14}$'
      ORDER BY d.datname;")" || return 1
  while IFS='|' read -r name active; do
    [[ -n "${name}" ]] || continue
    valid_drill_name "${name}" || return 78
    [[ "${active}" == f ]] || {
      echo "Refusing to remove an active restore-drill database: ${name}" >&2
      return 69
    }
    drop_drill_database "${name}" false || return 70
  done <<<"${listing//$'\r'/}"
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
    .schema_version == 2 and
    .raw_coordinates_included == false and
    .device_health_rows_included == false and
    .attributable_quiz_feedback_included == false and
    .feedback_operation_rows_included == false and
    .anonymous_review_rows_included == false
  ' "${PAIR_PATH}" >/dev/null || {
    echo "The coordinated backup pair manifest is invalid." >&2
    exit 78
  }
  [[ -f "${IDENTITY_PATH}" ]] || { echo "The age identity is unavailable." >&2; exit 66; }
}

restore_database() {
  local backup="$1"
  stack exec -T postgres createdb --username="${database_user}" "${DATABASE_NAME}"
  created_database=true
  "${AGE_BIN}" --decrypt --identity "${IDENTITY_PATH}" "${backup}" | \
    stack exec -T postgres pg_restore --no-owner --exit-on-error --single-transaction \
      --username="${database_user}" --dbname="${DATABASE_NAME}"
}

verify_database() {
  local result
  result="$(stack exec -T postgres psql --username="${database_user}" \
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
}

verify_attachments() {
  local backup="$1" verifier
  verifier="$(<"${SCRIPT_DIR}/verify-attachment-backup.py")"
  "${AGE_BIN}" --decrypt --identity "${IDENTITY_PATH}" "${backup}" | \
    stack run --rm -T --no-deps --entrypoint python attachment-init -c "${verifier}"
}

main() {
  local database_backup attachment_backup
  [[ -x "${AGE_BIN}" ]]; command -v jq >/dev/null; command -v sha256sum >/dev/null
  command -v findmnt >/dev/null; command -v mountpoint >/dev/null
  command -v flock >/dev/null
  unraid_storage_ready || {
    echo "The exact Unraid cache and user-share mounts are unavailable." >&2
    exit 69
  }
  exec 8>/var/lock/little-orbit-restore-drill.lock
  flock --nonblock 8 || { echo "Another restore drill is active." >&2; exit 69; }
  trap finish EXIT
  validate_pair
  database_user="$(stack exec -T postgres printenv POSTGRES_USER | tr -d '\r')"
  [[ -n "${database_user}" ]] || { echo "PostgreSQL user is unavailable." >&2; exit 69; }
  remove_stale_drill_databases
  database_backup="$(resolve_entry database)"
  attachment_backup="$(resolve_entry attachments)"
  verify_entry database "${database_backup}"
  verify_entry attachments "${attachment_backup}"
  restore_database "${database_backup}"
  verify_database
  verify_attachments "${attachment_backup}"
  cleanup
  jq -n --arg pair_manifest_sha256 "$(sha256sum "${PAIR_PATH}" | cut -d' ' -f1)" \
    '{database_schema:"0032",excluded_private_rows:"verified_empty",
      attachment_manifest:"verified",pair_manifest_sha256:$pair_manifest_sha256}'
}

main "$@"
