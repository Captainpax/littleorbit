#!/usr/bin/env bash
set -euo pipefail

readonly EXPECTED_ADDRESS="${LITTLE_ORBIT_HOST_ADDRESS:-192.168.50.14}"
readonly DATA_ROOT="${LITTLE_ORBIT_DATA_ROOT:-/mnt/cache/little-orbit-live}"
readonly DEPLOY_ROOT="${LITTLE_ORBIT_DEPLOY_PARENT:-/mnt/cache/little-orbit-deploy}"
readonly SECRET_ROOT="${LITTLE_ORBIT_SECRET_ROOT:-/mnt/cache/little-orbit-secrets}"
readonly BACKUP_ROOT="${LITTLE_ORBIT_BACKUP_ROOT:-/mnt/user/little-orbit-backups}"
readonly GPU_ROOT="${GPU_COORDINATOR_ROOT:-/mnt/cache/gpu-coordinator}"
readonly GPU_GID="${GPU_COORDINATOR_GID:-2000}"
readonly TOOL_ROOT="${LITTLE_ORBIT_TOOL_ROOT:-/mnt/cache/little-orbit-tools}"
readonly AGE_VERSION="1.3.2"
readonly AGE_SHA256="cbe24006683f8eb669266162894b9a522a1af52f2665fbc63a4bb032ed26ac10"
readonly SHARE_CONFIG_ROOT="/boot/config/shares"
readonly UNRAID_EMCMD="/usr/local/sbin/emcmd"
readonly SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"

source "${SCRIPT_DIR}/unraid-operation-lock.sh"

require_fixed_root() {
  local value="$1" expected="$2" label="$3"
  [[ "${value}" == "${expected}" ]] || {
    echo "${label} must use the fixed reviewed Unraid path." >&2
    exit 78
  }
  [[ ! -L "${value}" && (! -e "${value}" || -d "${value}") ]] || {
    echo "${label} must be a real directory, not a link or file." >&2
    exit 78
  }
}

require_unraid_mount() {
  local path="$1" expected_source="$2" expected_fstype="$3"
  local record target source fstype
  mountpoint --quiet -- "${path}" || return 1
  record="$(findmnt --noheadings --raw --mountpoint "${path}" \
    --output TARGET,SOURCE,FSTYPE)" || return 1
  read -r target source fstype <<<"${record}"
  [[ "${target}" == "${path}" && "${fstype}" == "${expected_fstype}" ]] || return 1
  case "${expected_source}" in
    device) [[ "${source}" == /dev/* ]] ;;
    shfs) [[ "${source}" == shfs ]] ;;
    *) return 1 ;;
  esac
}

require_target() {
  if [[ "$(id -u)" != "0" ]]; then
    echo "Unraid bootstrap must run as root." >&2
    exit 77
  fi
  if ! hostname -I | tr ' ' '\n' | grep -Fxq "${EXPECTED_ADDRESS}"; then
    echo "Refusing to initialize a host without ${EXPECTED_ADDRESS}." >&2
    exit 78
  fi
  command -v findmnt >/dev/null; command -v mountpoint >/dev/null
  [[ -x "${UNRAID_EMCMD}" ]] || {
    echo "The fixed Unraid management command is unavailable." >&2
    exit 69
  }
  require_unraid_mount /mnt/cache device btrfs &&
    require_unraid_mount /mnt/user shfs fuse.shfs || {
    echo "The exact Unraid cache and user-share mounts must be available." >&2
    exit 78
  }
  require_fixed_root "${DATA_ROOT}" /mnt/cache/little-orbit-live "Live data root"
  require_fixed_root "${DEPLOY_ROOT}" /mnt/cache/little-orbit-deploy "Deploy root"
  require_fixed_root "${SECRET_ROOT}" /mnt/cache/little-orbit-secrets "Secret root"
  require_fixed_root "${BACKUP_ROOT}" /mnt/user/little-orbit-backups "Backup root"
  require_fixed_root "${GPU_ROOT}" /mnt/cache/gpu-coordinator "GPU coordinator root"
  require_fixed_root "${TOOL_ROOT}" /mnt/cache/little-orbit-tools "Tool root"
}

configure_share() {
  local name="$1" use_cache="$2" pool="$3" description="$4" target temporary
  target="${SHARE_CONFIG_ROOT}/${name}.cfg"
  require_unambiguous_share_config "${name}" "${target}"
  if [[ -e "${target}" || -L "${target}" ]]; then
    upgrade_legacy_non_nfs_share "${target}" "${name}" "${use_cache}" "${pool}"
    validate_share_config "${target}" "${name}" "${use_cache}" "${pool}"
  else
    temporary="$(mktemp "${SHARE_CONFIG_ROOT}/.${name}.XXXXXX")"
    {
      printf 'shareComment="%s"\n' "${description}"
      printf 'shareInclude=""\nshareExclude=""\n'
      printf 'shareUseCache="%s"\nshareCachePool="%s"\nshareCachePool2=""\n' \
        "${use_cache}" "${pool}"
      printf 'shareCOW="auto"\nshareExport="-"\nshareCaseSensitive="auto"\n'
      printf 'shareSecurity="private"\nshareReadList=""\nshareWriteList=""\n'
      printf 'shareVolsizelimit=""\n'
      printf 'shareExportNFS="-"\nshareExportNFSFsid="0"\n'
      printf 'shareSecurityNFS="private"\nshareHostListNFS=""\n'
    } >"${temporary}"
    chmod 0600 "${temporary}"
    mv -- "${temporary}" "${target}"
    validate_share_config "${target}" "${name}" "${use_cache}" "${pool}"
  fi
  apply_share_runtime "${name}" "${use_cache}" "${pool}" "${description}"
  validate_share_config "${target}" "${name}" "${use_cache}" "${pool}"
}

render_share_apply_request() {
  local name="$1" use_cache="$2" pool="$3" description="$4" encoded_description
  local description_pattern='^[A-Za-z0-9 .-]+$'
  [[ "${name}" =~ ^[a-z0-9-]+$ && "${use_cache}" =~ ^(only|no)$ ]] || return 64
  [[ -z "${pool}" || "${pool}" == "cache" ]] || return 64
  [[ "${description}" =~ ${description_pattern} ]] || return 64
  encoded_description="${description// /+}"
  printf '%s' "cmdEditShare=Apply&shareNameOrig=${name}&shareName=${name}" \
    "&shareComment=${encoded_description}&shareFloor=0&shareUseCache=${use_cache}" \
    "&shareCachePool=${pool}&shareCachePool2=&shareAllocator=highwater" \
    "&shareSplitLevel=&shareInclude=&shareExclude=&shareCOW=auto"
}

apply_share_runtime() {
  local request
  request="$(render_share_apply_request "$@")" || {
    echo "The fixed share policy cannot be encoded safely." >&2
    exit 78
  }
  run_unraid_emcmd "${request}"
}

run_unraid_emcmd() {
  "${UNRAID_EMCMD}" "$1"
}

upgrade_legacy_non_nfs_share() {
  local target="$1" name="$2" use_cache="$3" pool="$4" temporary
  [[ -f "${target}" && ! -L "${target}" ]] || {
    echo "The ${name} share configuration must be one regular file, not a link." >&2
    exit 78
  }
  reject_duplicate_share_settings "${target}" "${name}"
  require_share_setting "${target}" "${name}" shareUseCache "${use_cache}"
  require_share_setting "${target}" "${name}" shareCachePool "${pool}"
  require_share_setting "${target}" "${name}" shareCachePool2 ""
  require_share_setting "${target}" "${name}" shareExport "-"
  require_share_setting "${target}" "${name}" shareSecurity "private"
  if grep -Eq '^[[:space:]]*share(ExportNFS|SecurityNFS)[[:space:]]*=' "${target}"; then
    return
  fi
  temporary="$(mktemp "${SHARE_CONFIG_ROOT}/.${name}.upgrade.XXXXXX")"
  cp -- "${target}" "${temporary}"
  if [[ -s "${temporary}" && -n "$(tail -c 1 -- "${temporary}")" ]]; then
    printf '\n' >>"${temporary}"
  fi
  printf 'shareExportNFS="-"\nshareSecurityNFS="private"\n' >>"${temporary}"
  chmod 0600 "${temporary}"
  mv -f -- "${temporary}" "${target}"
}

require_unambiguous_share_config() {
  local name="$1" target="$2" config_root="${3:-${SHARE_CONFIG_ROOT}}"
  local candidate filename match_count=0
  for candidate in "${config_root}"/*; do
    [[ -e "${candidate}" || -L "${candidate}" ]] || continue
    filename="${candidate##*/}"
    [[ "${filename,,}" == "${name,,}.cfg" ]] || continue
    match_count=$((match_count + 1))
    [[ "${candidate}" == "${target}" ]] || {
      echo "Ambiguous share configuration name for ${name}: ${filename}" >&2
      exit 78
    }
  done
  [[ "${match_count}" -le 1 ]] || {
    echo "Duplicate share configurations found for ${name}." >&2
    exit 78
  }
}

reject_duplicate_share_settings() {
  local target="$1" name="$2"
  awk '
    /^[[:space:]]*[[:alpha:]_][[:alnum:]_]*[[:space:]]*=/ {
      key = $0
      sub(/=.*/, "", key)
      gsub(/[[:space:]]/, "", key)
      key = tolower(key)
      if (++seen[key] > 1) exit 1
    }
  ' "${target}" || {
    echo "Duplicate settings make the ${name} share configuration ambiguous." >&2
    exit 78
  }
}

require_share_setting() {
  local target="$1" name="$2" key="$3" expected="$4"
  awk -v key="${key}" -v expected="${expected}" '
    {
      line = $0
      sub(/\r$/, "", line)
      if (line == key "=\"" expected "\"") exact++
      sub(/^[[:space:]]*/, "", line)
      if (substr(line, 1, length(key)) == key) {
        tail = substr(line, length(key) + 1)
        if (tail ~ /^[[:space:]]*=/) count++
      }
    }
    END { exit !(count == 1 && exact == 1) }
  ' "${target}" || {
      echo "The ${name} share has an ambiguous or unsafe ${key} setting." >&2
      exit 78
    }
}

validate_share_config() {
  local target="$1" name="$2" use_cache="$3" pool="$4"
  [[ -f "${target}" && ! -L "${target}" ]] || {
    echo "The ${name} share configuration must be one regular file, not a link." >&2
    exit 78
  }
  reject_duplicate_share_settings "${target}" "${name}"
  require_share_setting "${target}" "${name}" shareUseCache "${use_cache}"
  require_share_setting "${target}" "${name}" shareCachePool "${pool}"
  require_share_setting "${target}" "${name}" shareCachePool2 ""
  require_share_setting "${target}" "${name}" shareExport "-"
  require_share_setting "${target}" "${name}" shareSecurity "private"
  require_share_setting "${target}" "${name}" shareExportNFS "-"
  require_share_setting "${target}" "${name}" shareSecurityNFS "private"
}

require_array_disk_mount() {
  local storage_root="$1" storage_name="$2" record target source fstype number
  mountpoint --quiet -- "${storage_root}" || return 1
  record="$(findmnt --noheadings --raw --mountpoint "${storage_root}" \
    --output TARGET,SOURCE,FSTYPE)" || return 1
  read -r target source fstype <<<"${record}"
  [[ "${target}" == "${storage_root}" ]] || return 1
  number="${storage_name#disk}"
  case "${fstype}" in
    xfs|btrfs)
      [[ "${source}" =~ ^/dev/(mapper/)?md${number}(p1)?$ ]]
      ;;
    zfs)
      [[ "${source}" == "${storage_name}" || "${source}" == "${storage_name}/"* ]]
      ;;
    *) return 1 ;;
  esac
}

audit_share_placement() {
  local name="$1" policy="$2" mount_root="${3:-/mnt}" check_mounts="${4:-true}"
  local candidate physical_name storage_root storage_name allowed
  for storage_root in "${mount_root}"/*; do
    [[ -d "${storage_root}" || -L "${storage_root}" ]] || continue
    storage_name="${storage_root##*/}"
    [[ "${storage_name}" != "user" && "${storage_name}" != "user0" ]] || continue
    for candidate in "${storage_root}"/*; do
      [[ -e "${candidate}" || -L "${candidate}" ]] || continue
      physical_name="${candidate##*/}"
      [[ "${physical_name,,}" == "${name,,}" ]] || continue
      [[ "${physical_name}" == "${name}" ]] || {
        echo "The ${name} share has an ambiguous physical name: ${physical_name}" >&2
        exit 78
      }
      allowed="false"
      if [[ "${policy}" == "cache" && "${storage_name}" == "cache" ]]; then
        allowed="true"
      elif [[ "${policy}" == "array" && "${storage_name}" =~ ^disk[0-9]+$ ]]; then
        allowed="true"
      fi
      [[ "${allowed}" == "true" && -d "${candidate}" && ! -L "${candidate}" ]] || {
        echo "The ${name} share has data on the forbidden ${storage_name} tier." >&2
        exit 78
      }
      if [[ "${policy}" == "array" && "${check_mounts}" == "true" ]]; then
        require_array_disk_mount "${storage_root}" "${storage_name}" || {
          echo "The ${name} share is under an unverified array mount." >&2
          exit 78
        }
      fi
    done
  done
}

audit_all_share_placements() {
  local name
  for name in little-orbit-live little-orbit-deploy little-orbit-secrets \
    gpu-coordinator little-orbit-tools; do
    audit_share_placement "${name}" cache
  done
  audit_share_placement little-orbit-backups array
}

verify_share_placement() {
  local name="$1" policy="$2" mount_root="${3:-/mnt}" check_mounts="${4:-true}"
  local candidate found="false"
  audit_share_placement "${name}" "${policy}" "${mount_root}" "${check_mounts}"
  if [[ "${policy}" == "cache" ]]; then
    [[ -d "${mount_root}/cache/${name}" && ! -L "${mount_root}/cache/${name}" ]] || {
      echo "The ${name} share is missing from the reviewed cache pool." >&2
      exit 78
    }
    return
  fi
  for candidate in "${mount_root}"/disk[0-9]*/"${name}"; do
    [[ -d "${candidate}" && ! -L "${candidate}" ]] || continue
    found="true"
  done
  [[ "${policy}" == "array" && "${found}" == "true" ]] || {
    echo "The ${name} share is not physically present on an array disk." >&2
    exit 78
  }
}

verify_all_share_placements() {
  local name
  for name in little-orbit-live little-orbit-deploy little-orbit-secrets \
    gpu-coordinator little-orbit-tools; do
    verify_share_placement "${name}" cache
  done
  verify_share_placement little-orbit-backups array
}

configure_shares() {
  [[ -d "${SHARE_CONFIG_ROOT}" && ! -L "${SHARE_CONFIG_ROOT}" ]] || {
    echo "Unraid share configuration must be an available real directory." >&2
    exit 69
  }
  configure_share little-orbit-live only cache "Little Orbit direct-pool live state"
  configure_share little-orbit-deploy only cache "Little Orbit deployment source"
  configure_share little-orbit-secrets only cache "Little Orbit root-only runtime secrets"
  configure_share gpu-coordinator only cache "Content-free shared GPU coordination"
  configure_share little-orbit-tools only cache "Little Orbit pinned host tools"
  configure_share little-orbit-backups no "" "Little Orbit encrypted array backups"
}

create_layout() {
  install -d -m 0750 "${DATA_ROOT}" "${DEPLOY_ROOT}" "${BACKUP_ROOT}" "${TOOL_ROOT}"
  install -d -m 0700 "${SECRET_ROOT}"
  prepare_secret_root
  install -d -m 0700 -o 999 -g 70 "${DATA_ROOT}/postgres"
  install -d -m 0750 -o 65532 -g 65532 "${DATA_ROOT}/attachments"
  install -d -m 0755 "${DATA_ROOT}/releases" "${DATA_ROOT}/ollama"
  install -d -m 0755 -o 1000 -g 1000 "${DATA_ROOT}/clamav"
  prepare_backup_placement_sentinel
  prepare_gpu_lock
}

prepare_secret_root() {
  [[ -d "${SECRET_ROOT}" && ! -L "${SECRET_ROOT}" ]] || {
    echo "The runtime secrets root must be a real directory." >&2
    exit 78
  }
  chown --no-dereference 0:0 "${SECRET_ROOT}"
  chmod 0700 "${SECRET_ROOT}"
  [[ "$(stat -c '%F:%u:%g:%a' "${SECRET_ROOT}")" == \
    "directory:0:0:700" ]] || {
    echo "The runtime secrets root ownership or mode is unsafe." >&2
    exit 78
  }
}

prepare_backup_placement_sentinel() {
  local sentinel="${BACKUP_ROOT}/.array-placement"
  [[ ! -L "${sentinel}" ]] || {
    echo "The backup placement sentinel cannot be a symbolic link." >&2
    exit 78
  }
  if [[ ! -e "${sentinel}" ]]; then
    (umask 0077; set -o noclobber; printf 'little-orbit-array-only\n' >"${sentinel}") || {
      echo "Could not create the backup placement sentinel." >&2
      exit 73
    }
  fi
  [[ "$(stat -c '%F:%u:%g:%a:%h' "${sentinel}")" == \
    "regular file:0:0:600:1" ]] || {
    echo "The backup placement sentinel metadata is unsafe." >&2
    exit 78
  }
  [[ "$(<"${sentinel}")" == "little-orbit-array-only" ]] || {
    echo "The backup placement sentinel content is invalid." >&2
    exit 78
  }
}

prepare_gpu_lock() {
  local lock_path="${GPU_ROOT}/gpu.lock" metadata
  [[ ! -L "${GPU_ROOT}" && (! -e "${GPU_ROOT}" || -d "${GPU_ROOT}") ]] || {
    echo "The GPU coordinator root must be a real directory." >&2
    exit 78
  }
  install -d -m 2750 -o 0 -g "${GPU_GID}" "${GPU_ROOT}"
  chown --no-dereference 0:"${GPU_GID}" "${GPU_ROOT}"
  chmod 2750 "${GPU_ROOT}"
  [[ ! -L "${lock_path}" ]] || {
    echo "Refusing a symbolic GPU lock path." >&2
    exit 78
  }
  if [[ ! -e "${lock_path}" ]]; then
    (umask 0006; set -o noclobber; : >"${lock_path}") || {
      echo "Could not create the stable GPU lock inode." >&2
      exit 73
    }
  fi
  [[ -f "${lock_path}" && ! -L "${lock_path}" ]] || {
    echo "The GPU lock must be a regular file." >&2
    exit 78
  }
  metadata="$(stat --format='%h:%s' -- "${lock_path}")"
  [[ "${metadata}" == "1:0" ]] || {
    echo "The GPU lock must be an empty, single-link inode." >&2
    exit 78
  }
  chown --no-dereference 0:"${GPU_GID}" "${lock_path}"
  chmod 0660 "${lock_path}"
  [[ "$(stat --format='%u:%g:%a:%h:%s' -- "${lock_path}")" == \
    "0:${GPU_GID}:660:1:0" ]] || {
    echo "The GPU lock ownership or mode is unsafe." >&2
    exit 78
  }
  chmod 3770 "${GPU_ROOT}"
}

install_age() (
  local age_bin="${TOOL_ROOT}/bin/age" archive temporary
  if [[ -x "${age_bin}" ]] && "${age_bin}" --version | grep -Fq "${AGE_VERSION}"; then
    return
  fi
  command -v curl >/dev/null; command -v sha256sum >/dev/null; command -v tar >/dev/null
  temporary="$(mktemp -d "${TOOL_ROOT}/.age-install-XXXXXX")"
  trap 'rm -rf -- "${temporary}"' EXIT
  archive="${temporary}/age.tar.gz"
  curl --fail --location --proto '=https' --tlsv1.2 \
    --output "${archive}" \
    "https://github.com/FiloSottile/age/releases/download/v${AGE_VERSION}/age-v${AGE_VERSION}-linux-amd64.tar.gz"
  printf '%s  %s\n' "${AGE_SHA256}" "${archive}" | sha256sum --check --status
  tar -xzf "${archive}" -C "${temporary}"
  install -d -m 0750 "${TOOL_ROOT}/bin"
  install -m 0755 "${temporary}/age/age" "${TOOL_ROOT}/bin/age"
  install -m 0755 "${temporary}/age/age-keygen" "${TOOL_ROOT}/bin/age-keygen"
)

main() {
  acquire_little_orbit_operations_lock wait 300 || {
    echo "Operations lock wait timed out." >&2
    return 75
  }
  require_target
  audit_all_share_placements
  configure_shares
  create_layout
  verify_all_share_placements
  install_age
  printf '{"outcome":"initialized","address":"%s"}\n' "${EXPECTED_ADDRESS}"
}

if [[ "${BASH_SOURCE[0]}" == "$0" ]]; then
  main "$@"
fi
