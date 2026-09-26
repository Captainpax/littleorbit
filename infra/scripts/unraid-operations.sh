#!/usr/bin/env bash
set -euo pipefail

readonly MODE="${1:-pending}"
readonly SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
readonly STACK="${SCRIPT_DIR}/unraid-stack.sh"
readonly LOCK_PATH="${LITTLE_ORBIT_OPERATIONS_LOCK:-/var/lock/little-orbit-operations.lock}"

stack() {
  bash "${STACK}" "$@"
}

db_identity() {
  local user database
  user="$(stack exec -T postgres printenv POSTGRES_USER | tr -d '\r')"
  database="$(stack exec -T postgres printenv POSTGRES_DB | tr -d '\r')"
  printf '%s|%s' "${user}" "${database}"
}

db_sql() {
  local identity user database
  identity="$(db_identity)"; user="${identity%%|*}"; database="${identity#*|}"
  stack exec -T postgres psql --username="${user}" --dbname="${database}" \
    --no-align --tuples-only --set=ON_ERROR_STOP=1 --command="$1"
}

start_run() {
  local kind="$1" job_id="${2:-}" run_id job_value
  run_id="$(cat /proc/sys/kernel/random/uuid)"
  job_value="NULL"
  [[ -z "${job_id}" ]] || job_value="'${job_id}'::uuid"
  db_sql "INSERT INTO backup_runs
    (id,job_request_id,kind,status,destination,details_json,created_at)
    VALUES ('${run_id}'::uuid,${job_value},'${kind}','running','local_encrypted','{}'::json,now());" \
    >/dev/null
  printf '%s' "${run_id}"
}

finish_run() {
  local run_id="$1" status="$2" digest="${3:-}" details="$4" digest_sql="NULL"
  [[ -z "${digest}" ]] || digest_sql="'${digest}'"
  db_sql "UPDATE backup_runs SET status='${status}',manifest_sha256=${digest_sql},
    details_json='${details}'::json,finished_at=now() WHERE id='${run_id}'::uuid;" >/dev/null
}

finish_job() {
  local job_id="$1" status="$2" result="$3"
  [[ -n "${job_id}" ]] || return 0
  db_sql "UPDATE admin_job_requests SET status='${status}',result_json='${result}'::json,
    finished_at=now() WHERE id='${job_id}'::uuid AND status='running';" >/dev/null
}

run_backup() {
  local job_id="${1:-}" run_id output digest details
  run_id="$(start_run backup "${job_id}")"
  if output="$(bash "${SCRIPT_DIR}/unraid-backup.sh")"; then
    digest="$(sha256sum "$(jq -er .pair_manifest <<<"${output}")" | cut -d' ' -f1)"
    details='{"coordinated_pair":true,"off_host_copy":false,"private_feedback_included":false,"raw_coordinates_included":false}'
    finish_run "${run_id}" passed "${digest}" "${details}"
    finish_job "${job_id}" passed '{"outcome":"backup_completed"}'
    printf '%s\n' "${output}"
  else
    finish_run "${run_id}" failed '' '{"reason":"backup_failed"}'
    finish_job "${job_id}" failed '{"reason":"backup_failed"}'
    return 1
  fi
}

run_restore_drill() {
  local job_id="${1:-}" run_id output digest
  run_id="$(start_run test_restore "${job_id}")"
  if output="$(bash "${SCRIPT_DIR}/unraid-restore-drill.sh")"; then
    digest="$(jq -er .pair_manifest_sha256 <<<"${output}")"
    finish_run "${run_id}" passed "${digest}" \
      '{"database_schema":"0032","excluded_private_rows":"verified_empty","attachment_manifest":"verified"}'
    finish_job "${job_id}" passed '{"outcome":"restore_drill_completed"}'
    printf '%s\n' "${output}"
  else
    finish_run "${run_id}" failed '' '{"reason":"restore_drill_failed"}'
    finish_job "${job_id}" failed '{"reason":"restore_drill_failed"}'
    return 1
  fi
}

claim_job() {
  db_sql "WITH candidate AS (
    SELECT id FROM admin_job_requests WHERE status='pending'
      AND kind IN ('backup','test_restore') ORDER BY created_at
      FOR UPDATE SKIP LOCKED LIMIT 1)
    UPDATE admin_job_requests jobs SET status='running',started_at=now()
    FROM candidate WHERE jobs.id=candidate.id
    RETURNING jobs.id::text || '|' || jobs.kind;" | tr -d '\r'
}

run_pending() {
  local claimed job_id kind
  for _ in 1 2 3 4 5; do
    claimed="$(claim_job)"; [[ -n "${claimed}" ]] || break
    job_id="${claimed%%|*}"; kind="${claimed#*|}"
    [[ "${job_id}" =~ ^[0-9a-f-]{36}$ ]] || { echo "Malformed job claim." >&2; return 65; }
    case "${kind}" in
      backup) run_backup "${job_id}" ;;
      test_restore) run_restore_drill "${job_id}" ;;
      *) echo "Unexpected job kind." >&2; return 65 ;;
    esac
  done
}

main() {
  install -d -m 0755 "$(dirname "${LOCK_PATH}")"
  exec 9>"${LOCK_PATH}"
  if [[ "${MODE}" == pending ]]; then
    flock -n 9 || { echo '{"outcome":"already_running"}'; return 0; }
  else
    flock -w 300 9 || { echo "Operations lock wait timed out." >&2; return 75; }
  fi
  db_sql "UPDATE admin_job_requests SET status='failed',result_json='{\"reason\":\"runner_interrupted\"}'::json,
    finished_at=now() WHERE status='running' AND kind IN ('backup','test_restore')
    AND started_at < now() - interval '2 hours';
    UPDATE backup_runs SET status='failed',details_json='{\"reason\":\"runner_interrupted\"}'::json,
    finished_at=now() WHERE status='running' AND created_at < now() - interval '2 hours';" >/dev/null
  case "${MODE}" in
    pending) run_pending ;;
    backup) run_backup ;;
    test_restore) run_restore_drill ;;
    *) echo "Usage: $0 {pending|backup|test_restore}" >&2; return 64 ;;
  esac
}

main "$@"
