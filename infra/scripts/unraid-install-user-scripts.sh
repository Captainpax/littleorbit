#!/usr/bin/env bash
set -euo pipefail

readonly EXPECTED_ADDRESS="${LITTLE_ORBIT_HOST_ADDRESS:-192.168.50.14}"
readonly PLUGIN_ROOT="/boot/config/plugins/user.scripts"
readonly SCRIPT_ROOT="${PLUGIN_ROOT}/scripts"
readonly SCHEDULE_PATH="${PLUGIN_ROOT}/schedule.json"
readonly CUSTOM_CRON_PATH="${PLUGIN_ROOT}/customSchedule.cron"
readonly ENTRYPOINT="/mnt/cache/little-orbit-deploy/repo/infra/scripts/unraid-user-script.sh"
readonly SOURCE_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
readonly -a MANAGED_CRON_LINES=(
  "*/5 * * * * /usr/local/emhttp/plugins/user.scripts/startCustom.php ${SCRIPT_ROOT}/little-orbit-pending/script > /dev/null 2>&1"
  "0 8 * * * /usr/local/emhttp/plugins/user.scripts/startCustom.php ${SCRIPT_ROOT}/little-orbit-backup/script > /dev/null 2>&1"
  "0 7 * * 2 /usr/local/emhttp/plugins/user.scripts/startCustom.php ${SCRIPT_ROOT}/little-orbit-restore-drill/script > /dev/null 2>&1"
)

source "${SOURCE_DIR}/unraid-timezone.sh"
source "${SOURCE_DIR}/unraid-operation-lock.sh"

require_target() {
  [[ "$(id -u)" == "0" ]] || { echo "User Scripts setup must run as root." >&2; exit 77; }
  hostname -I | tr ' ' '\n' | grep -Fxq "${EXPECTED_ADDRESS}" || {
    echo "Refusing to alter User Scripts on an unexpected host." >&2
    exit 78
  }
  require_unraid_pacific_timezone
  [[ -d "${SCRIPT_ROOT}" && -f "${SCHEDULE_PATH}" ]] || {
    echo "The Unraid User Scripts plugin is unavailable." >&2
    exit 69
  }
  command -v jq >/dev/null
  command -v perl >/dev/null
  command -v tail >/dev/null
  command -v od >/dev/null
}

install_wrapper() {
  local name="$1" mode="$2" description="$3" directory partial
  directory="${SCRIPT_ROOT}/${name}"
  install -d -m 0755 "${directory}"
  partial="$(mktemp "${directory}/.script.XXXXXX")"
  printf '#!/usr/bin/env bash\nexec bash %q %q\n' "${ENTRYPOINT}" "${mode}" >"${partial}"
  chmod 0755 "${partial}"
  mv -f -- "${partial}" "${directory}/script"
  printf '%s\n' "${description}" >"${directory}/description"
}

render_schedule_document() {
  local schedule_path="$1" temporary="$2" script_root="$3"
  local startup_frequency="$4" custom_frequency="$5"
  local pending="$6" backup="$7" drill="$8"
  jq --arg root "${script_root}" --arg startup "${startup_frequency}" \
    --arg custom_frequency "${custom_frequency}" --arg pending "${pending}" \
    --arg backup "${backup}" --arg drill "${drill}" '
      def schedule($path; $frequency; $custom): {
        script: $path,
        frequency: $frequency,
        id: ("schedule" + ($path | split("/")[-2])),
        custom: $custom
      };
      def script_path:
        .value |
        if type == "object" and ((.script? | type) == "string") then
          .script
        else
          ""
        end;
      def mentions_owned_namespace:
        (.key | contains("/little-orbit-")) or
        (script_path | contains("/little-orbit-"));
      def is_exact_owned($owned):
        .key as $key |
        script_path as $script |
        ($key == $script) and (($owned | index($key)) != null);
      ($root + "/little-orbit-startup/script") as $startup_path |
      ($root + "/little-orbit-pending/script") as $pending_path |
      ($root + "/little-orbit-backup/script") as $backup_path |
      ($root + "/little-orbit-restore-drill/script") as $drill_path |
      [$startup_path, $pending_path, $backup_path, $drill_path] as $owned |
      to_entries as $entries |
      if any($entries[]; mentions_owned_namespace and (is_exact_owned($owned) | not))
      then error("ambiguous Little Orbit User Scripts schedule")
      else
        ($entries |
          map(.key as $key | select(($owned | index($key)) == null)) |
          from_entries)
      end |
      .[$startup_path] = schedule($startup_path; $startup; "") |
      .[$pending_path] = schedule($pending_path; $custom_frequency; $pending) |
      .[$backup_path] = schedule($backup_path; $custom_frequency; $backup) |
      .[$drill_path] = schedule($drill_path; $custom_frequency; $drill)
    ' "${schedule_path}" >"${temporary}"
}

write_schedules() {
  local mode="$1" schedule_path="${2:-${SCHEDULE_PATH}}"
  local script_root="${3:-${SCRIPT_ROOT}}"
  local startup_frequency="disabled" custom_frequency="disabled"
  local pending="" backup="" drill="" temporary
  if [[ "${mode}" == "activate-after-cutover" ]]; then
    startup_frequency="start"
    custom_frequency="custom"
    pending="*/5 * * * *"
    backup="0 8 * * *"
    drill="0 7 * * 2"
  fi
  temporary="$(mktemp "${schedule_path%/*}/.schedule.XXXXXX")"
  if ! render_schedule_document \
    "${schedule_path}" "${temporary}" "${script_root}" \
    "${startup_frequency}" "${custom_frequency}" \
    "${pending}" "${backup}" "${drill}"; then
    rm -f -- "${temporary}"
    echo "The User Scripts schedule contains an ambiguous Little Orbit entry." >&2
    exit 78
  fi
  mv -f -- "${temporary}" "${schedule_path}"
}

remove_managed_cron_lines() {
  local path="${1:-${CUSTOM_CRON_PATH}}" directory temporary
  [[ ! -L "${path}" && (! -e "${path}" || -f "${path}") ]] || {
    echo "The User Scripts custom cron path must be a regular file, not a link." >&2
    exit 78
  }
  [[ -f "${path}" ]] || return 0
  directory="${path%/*}"
  temporary="$(mktemp "${directory}/.customSchedule.XXXXXX")"
  if ! perl -e '
    use strict;
    use warnings;
    my ($source, $destination, @managed) = @ARGV;
    open my $input, "<:raw", $source or exit 2;
    local $/;
    my $contents = <$input>;
    close $input or exit 3;
    $contents = "" unless defined $contents;
    for my $line (@managed) {
      $contents =~ s/(?:\A|(?<=\n)|(?<=\r))\Q$line\E(?:\r\n|\n|\r|\z)//g;
    }
    open my $output, ">:raw", $destination or exit 4;
    print {$output} $contents or exit 5;
    close $output or exit 6;
  ' "${path}" "${temporary}" "${MANAGED_CRON_LINES[@]}"; then
    rm -f -- "${temporary}"
    echo "Could not safely remove the Little Orbit cron entries." >&2
    exit 74
  fi
  if grep -Eq -- 'little-orbit-(startup|pending|backup|restore-drill)' \
    "${temporary}"; then
    rm -f -- "${temporary}"
    echo "An unrecognized Little Orbit cron entry must be resolved manually." >&2
    exit 78
  fi
  chmod 0600 "${temporary}"
  mv -f -- "${temporary}" "${path}"
}

activate_cron() {
  local path="${1:-${CUSTOM_CRON_PATH}}" last_byte line line_ending=$'\n'
  remove_managed_cron_lines "${path}"
  if [[ ! -e "${path}" ]]; then
    printf '%s\n' '# Generated cron schedule for user.scripts' >"${path}"
    chmod 0600 "${path}"
  fi
  while IFS= read -r line || [[ -n "${line}" ]]; do
    if [[ "${line}" == *$'\r' ]]; then
      line_ending=$'\r\n'
      break
    fi
  done <"${path}"
  if [[ -s "${path}" ]]; then
    last_byte="$(tail -c 1 -- "${path}" | od -An -tu1 | tr -d '[:space:]')"
    if [[ "${last_byte}" == "13" ]]; then
      printf '\n' >>"${path}"
    elif [[ "${last_byte}" != "10" ]]; then
      printf '%s' "${line_ending}" >>"${path}"
    fi
  fi
  for line in "${MANAGED_CRON_LINES[@]}"; do
    printf '%s%s' "${line}" "${line_ending}"
  done >>"${path}"
}

apply_scheduler() {
  install -d -m 0755 /tmp/user.scripts
  cp -- "${SCHEDULE_PATH}" /tmp/user.scripts/schedule.json
  /usr/local/sbin/update_cron
}

main() {
  local mode="${1:-install}" outcome
  [[ "$#" -le 1 ]] || {
    echo "Usage: $0 [install|activate-after-cutover]" >&2
    exit 64
  }
  case "${mode}" in
    install) outcome="installed-inactive" ;;
    activate-after-cutover) outcome="activated" ;;
    *)
      echo "Usage: $0 [install|activate-after-cutover]" >&2
      exit 64
      ;;
  esac
  acquire_little_orbit_operations_lock wait 300 || {
    echo "Operations lock wait timed out." >&2
    return 75
  }
  require_target
  install_wrapper little-orbit-startup startup \
    "Apply the NPM-only firewall and start the fixed Little Orbit Compose stack."
  install_wrapper little-orbit-pending pending \
    "Run allowlisted pending Little Orbit operations."
  install_wrapper little-orbit-backup backup \
    "Create the daily privacy-filtered encrypted backup pair."
  install_wrapper little-orbit-restore-drill test_restore \
    "Verify the newest encrypted pair without changing live state."
  write_schedules "${mode}"
  if [[ "${mode}" == "activate-after-cutover" ]]; then
    activate_cron
  else
    remove_managed_cron_lines
  fi
  apply_scheduler
  printf '{"outcome":"%s","timezone":"%s"}\n' \
    "${outcome}" "${LITTLE_ORBIT_SCHEDULE_TIMEZONE}"
}

if [[ "${BASH_SOURCE[0]}" == "$0" ]]; then
  main "$@"
fi
