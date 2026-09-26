#!/usr/bin/env bash
set -euo pipefail

readonly EXPECTED_ADDRESS="${LITTLE_ORBIT_HOST_ADDRESS:-192.168.50.14}"
readonly PLUGIN_ROOT="/boot/config/plugins/user.scripts"
readonly SCRIPT_ROOT="${PLUGIN_ROOT}/scripts"
readonly SCHEDULE_PATH="${PLUGIN_ROOT}/schedule.json"
readonly ENTRYPOINT="/mnt/cache/little-orbit-deploy/repo/infra/scripts/unraid-user-script.sh"

require_target() {
  [[ "$(id -u)" == "0" ]] || { echo "User Scripts setup must run as root." >&2; exit 77; }
  hostname -I | tr ' ' '\n' | grep -Fxq "${EXPECTED_ADDRESS}" || {
    echo "Refusing to alter User Scripts on an unexpected host." >&2
    exit 78
  }
  [[ -d "${SCRIPT_ROOT}" && -f "${SCHEDULE_PATH}" ]] || {
    echo "The Unraid User Scripts plugin is unavailable." >&2
    exit 69
  }
  command -v jq >/dev/null
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

update_schedule() {
  local name="$1" frequency="$2" custom="$3" path temporary
  path="${SCRIPT_ROOT}/${name}/script"
  temporary="$(mktemp "${PLUGIN_ROOT}/.schedule.XXXXXX")"
  jq --arg path "${path}" --arg frequency "${frequency}" \
    --arg id "schedule${name}" --arg custom "${custom}" \
    '.[$path]={script:$path,frequency:$frequency,id:$id,custom:$custom}' \
    "${SCHEDULE_PATH}" >"${temporary}"
  mv -f -- "${temporary}" "${SCHEDULE_PATH}"
}

refresh_cron() {
  local partial
  partial="$(mktemp "${PLUGIN_ROOT}/.customSchedule.XXXXXX")"
  {
    printf '%s\n' '# Generated cron schedule for user.scripts'
    jq -r 'to_entries[] | select(.value.frequency == "custom") |
      select(.value.custom != "") |
      "\(.value.custom) /usr/local/emhttp/plugins/user.scripts/startCustom.php \(.value.script) > /dev/null 2>&1"' \
      "${SCHEDULE_PATH}"
    printf '\n'
  } >"${partial}"
  mv -f -- "${partial}" "${PLUGIN_ROOT}/customSchedule.cron"
  install -d -m 0755 /tmp/user.scripts
  cp -- "${SCHEDULE_PATH}" /tmp/user.scripts/schedule.json
  /usr/local/sbin/update_cron
}

main() {
  require_target
  install_wrapper little-orbit-startup startup \
    "Apply the NPM-only firewall and start the fixed Little Orbit Compose stack."
  install_wrapper little-orbit-pending pending \
    "Run allowlisted pending Little Orbit operations."
  install_wrapper little-orbit-backup backup \
    "Create the daily privacy-filtered encrypted backup pair."
  install_wrapper little-orbit-restore-drill test_restore \
    "Verify the newest encrypted pair without changing live state."
  update_schedule little-orbit-startup start ""
  update_schedule little-orbit-pending custom "*/5 * * * *"
  update_schedule little-orbit-backup custom "0 8 * * *"
  update_schedule little-orbit-restore-drill custom "0 7 * * 2"
  refresh_cron
  printf '{"outcome":"configured","timezone":"%s"}\n' "$(date +%Z)"
}

main "$@"
