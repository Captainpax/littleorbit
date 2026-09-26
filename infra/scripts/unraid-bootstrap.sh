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
  require_unraid_mount /mnt/cache device btrfs &&
    require_unraid_mount /mnt/user shfs fuse.shfs || {
    echo "The exact Unraid cache and user-share mounts must be available." >&2
    exit 78
  }
}

configure_share() {
  local name="$1" use_cache="$2" pool="$3" description="$4" target temporary
  target="${SHARE_CONFIG_ROOT}/${name}.cfg"
  temporary="$(mktemp "${SHARE_CONFIG_ROOT}/.${name}.XXXXXX")"
  {
    printf 'shareComment="%s"\n' "${description}"
    printf 'shareInclude=""\nshareExclude=""\n'
    printf 'shareUseCache="%s"\nshareCachePool="%s"\nshareCachePool2=""\n' \
      "${use_cache}" "${pool}"
    printf 'shareCOW="auto"\nshareExport="-"\nshareCaseSensitive="auto"\n'
    printf 'shareSecurity="private"\nshareReadList=""\nshareWriteList=""\n'
    printf 'shareVolsizelimit=""\n'
  } >"${temporary}"
  if [[ -f "${target}" ]]; then
    rm -f -- "${temporary}"
    grep -Fqx -- "shareUseCache=\"${use_cache}\"" "${target}" &&
      grep -Fqx -- "shareCachePool=\"${pool}\"" "${target}" &&
      grep -Fqx -- 'shareExport="-"' "${target}" &&
      grep -Fqx -- 'shareSecurity="private"' "${target}" || {
        echo "Existing share configuration violates the required storage/export policy: ${name}" >&2
        exit 78
      }
    return
  fi
  chmod 0600 "${temporary}"
  mv -- "${temporary}" "${target}"
}

configure_shares() {
  [[ -d "${SHARE_CONFIG_ROOT}" ]] || {
    echo "Unraid share configuration is unavailable." >&2
    exit 69
  }
  configure_share little-orbit-live only cache "Little Orbit direct-pool live state"
  configure_share little-orbit-deploy only cache "Little Orbit deployment source"
  configure_share little-orbit-secrets only cache "Little Orbit root-only runtime secrets"
  configure_share gpu-coordinator only cache "Content-free shared GPU coordination"
  configure_share little-orbit-backups no "" "Little Orbit encrypted array backups"
}

create_layout() {
  install -d -m 0750 "${DATA_ROOT}" "${DEPLOY_ROOT}" "${BACKUP_ROOT}" "${TOOL_ROOT}"
  install -d -m 0700 "${SECRET_ROOT}"
  install -d -m 0700 -o 999 -g 70 "${DATA_ROOT}/postgres"
  install -d -m 0750 -o 65532 -g 65532 "${DATA_ROOT}/attachments"
  install -d -m 0755 "${DATA_ROOT}/releases" "${DATA_ROOT}/ollama"
  install -d -m 0755 -o 1000 -g 1000 "${DATA_ROOT}/clamav"
  prepare_gpu_lock
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

require_target
configure_shares
create_layout
install_age
printf '{"outcome":"initialized","address":"%s"}\n' "${EXPECTED_ADDRESS}"
