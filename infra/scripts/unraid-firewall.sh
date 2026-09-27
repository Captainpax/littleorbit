#!/usr/bin/env bash
set -euo pipefail

readonly EXPECTED_ADDRESS="192.168.50.14"
readonly PROXY_ADDRESS="192.168.50.6"
readonly PUBLISHED_PORT="8180"
readonly CHAIN_A="LITTLE_ORBIT_GATEWAY_A"
readonly CHAIN_B="LITTLE_ORBIT_GATEWAY_B"
readonly MODE="${1:-verify}"
readonly SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"

source "${SCRIPT_DIR}/unraid-operation-lock.sh"

require_target() {
  [[ "$(id -u)" == "0" ]] || { echo "Firewall setup must run as root." >&2; exit 77; }
  hostname -I | tr ' ' '\n' | grep -Fxq "${EXPECTED_ADDRESS}" || {
    echo "Refusing to alter firewall rules on an unexpected host." >&2
    exit 78
  }
  iptables -nL DOCKER-USER >/dev/null 2>&1 || {
    echo "Docker's DOCKER-USER chain is unavailable." >&2
    exit 69
  }
}

has_jump() {
  iptables -C DOCKER-USER -j "$1" >/dev/null 2>&1
}

remove_jumps() {
  local chain="$1"
  while has_jump "${chain}"; do
    iptables -D DOCKER-USER -j "${chain}"
  done
}

populate_chain() {
  local chain="$1"
  iptables -N "${chain}" 2>/dev/null || true
  iptables -F "${chain}"
  iptables -A "${chain}" -p tcp \
    -m conntrack --ctstate ESTABLISHED,RELATED --ctdir REPLY \
    --ctorigsrc "${PROXY_ADDRESS}" --ctorigdst "${EXPECTED_ADDRESS}" \
    --ctorigdstport "${PUBLISHED_PORT}" -j ACCEPT
  iptables -A "${chain}" -p tcp -s "${PROXY_ADDRESS}" \
    -m conntrack --ctdir ORIGINAL --ctorigdst "${EXPECTED_ADDRESS}" \
    --ctorigdstport "${PUBLISHED_PORT}" \
    -j ACCEPT
  iptables -A "${chain}" -p tcp \
    -m conntrack --ctdir ORIGINAL --ctorigdst "${EXPECTED_ADDRESS}" \
    --ctorigdstport "${PUBLISHED_PORT}" \
    -j REJECT --reject-with tcp-reset
  iptables -A "${chain}" -j RETURN
}

replace_owned_chain() {
  local current next first_rule
  if has_jump "${CHAIN_A}"; then
    current="${CHAIN_A}"
    next="${CHAIN_B}"
  else
    current="${CHAIN_B}"
    next="${CHAIN_A}"
  fi
  remove_jumps "${next}"
  populate_chain "${next}"
  iptables -I DOCKER-USER 1 -j "${next}"
  remove_jumps "${current}"
  if iptables -nL "${current}" >/dev/null 2>&1; then
    iptables -F "${current}"
  fi
  first_rule="$(iptables -S DOCKER-USER | awk '$1 == "-A" {print; exit}')"
  [[ "${first_rule}" == "-A DOCKER-USER -j ${next}" ]] || {
    echo "The Little Orbit firewall jump is not first in DOCKER-USER." >&2
    exit 69
  }
}

verify_no_ipv6_listener() {
  if ss -H -lnt6 "sport = :${PUBLISHED_PORT}" | grep -q .; then
    echo "An IPv6 listener exposes the Little Orbit gateway port." >&2
    exit 69
  fi
}

verify_exact_ipv4_listener() {
  local address
  while read -r address; do
    [[ -n "${address}" ]] || continue
    [[ "${address}" == "${EXPECTED_ADDRESS}:${PUBLISHED_PORT}" ]] || {
      echo "An unexpected IPv4 listener exposes the Little Orbit gateway port." >&2
      exit 69
    }
  done < <(ss -H -lnt4 "sport = :${PUBLISHED_PORT}" | awk '{print $4}')
}

verify_running_exposure_model() {
  local -a container_ids=()
  command -v jq >/dev/null || {
    echo "jq is required to verify the running Docker exposure model." >&2
    exit 69
  }
  mapfile -t container_ids < <(docker ps --all --quiet \
    --filter label=com.docker.compose.project=little-orbit)
  ((${#container_ids[@]} > 0)) || {
    echo "The Little Orbit Compose project has no containers to verify." >&2
    exit 69
  }
  docker inspect "${container_ids[@]}" | jq -e \
    --arg address "${EXPECTED_ADDRESS}" --arg port "${PUBLISHED_PORT}" '
      ([.[] | select(.Config.Labels["com.docker.compose.service"] == "gateway")]
        | length) == 1 and
      all(.[];
        if .Config.Labels["com.docker.compose.service"] == "gateway" then
          (.HostConfig.PortBindings == {
            (($port + "/tcp")): [{HostIp:$address, HostPort:$port}]
          })
        else
          ((.HostConfig.PortBindings // {}) | length) == 0
        end)
    ' >/dev/null || {
      echo "The running Docker model violates the single fixed gateway exposure." >&2
      exit 78
    }
}

main() {
  acquire_little_orbit_operations_lock wait 300 || {
    echo "Operations lock wait timed out." >&2
    return 75
  }
  require_target
  [[ "${MODE}" == verify || "${MODE}" == --prepare ]] || {
    echo "Usage: $0 [--prepare]" >&2
    return 64
  }
  replace_owned_chain
  verify_no_ipv6_listener
  verify_exact_ipv4_listener
  if [[ "${MODE}" == verify ]]; then
    verify_running_exposure_model
  fi
  printf '{"outcome":"configured","source":"%s","port":%s}\n' \
    "${PROXY_ADDRESS}" "${PUBLISHED_PORT}"
}

if [[ "${BASH_SOURCE[0]}" == "$0" ]]; then
  main "$@"
fi
