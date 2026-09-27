#!/usr/bin/env bash

readonly LITTLE_ORBIT_SCHEDULE_TIMEZONE="America/Los_Angeles"

configured_unraid_timezone() {
  local config_path="${1:-/boot/config/ident.cfg}"
  [[ -r "${config_path}" ]] || return 1
  awk -F= '
    {
      key=$1
      gsub(/^[[:space:]]+|[[:space:]]+$/, "", key)
    }
    key == "timeZone" {
      value=substr($0, index($0, "=") + 1)
      sub(/\r$/, "", value)
      gsub(/^[[:space:]]+|[[:space:]]+$/, "", value)
      if (value ~ /^".*"$/) {
        value=substr(value, 2, length(value) - 2)
      }
      print value
      found=1
      exit
    }
    END { if (!found) exit 1 }
  ' "${config_path}"
}

require_unraid_pacific_timezone() {
  local config_path="${1:-/boot/config/ident.cfg}"
  local localtime_path="${2:-/etc/localtime}"
  local zoneinfo_path="${3:-/usr/share/zoneinfo/${LITTLE_ORBIT_SCHEDULE_TIMEZONE}}"
  local configured

  command -v awk >/dev/null && command -v cmp >/dev/null || {
    echo "Timezone verification tools are unavailable." >&2
    return 69
  }
  configured="$(configured_unraid_timezone "${config_path}")" || {
    echo "The configured Unraid timezone could not be read." >&2
    return 78
  }
  [[ "${configured}" == "${LITTLE_ORBIT_SCHEDULE_TIMEZONE}" ]] || {
    echo "Unraid must be configured for ${LITTLE_ORBIT_SCHEDULE_TIMEZONE}; found ${configured}." >&2
    return 78
  }
  [[ -r "${localtime_path}" && -r "${zoneinfo_path}" ]] || {
    echo "The effective host timezone files are unavailable." >&2
    return 78
  }
  cmp -s -- "${localtime_path}" "${zoneinfo_path}" || {
    echo "The effective host timezone does not match ${LITTLE_ORBIT_SCHEDULE_TIMEZONE}." >&2
    return 78
  }
}
