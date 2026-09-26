#!/usr/bin/env bash
set -euo pipefail

readonly EXPECTED_ADDRESS="${LITTLE_ORBIT_HOST_ADDRESS:-192.168.50.14}"
readonly PROXY_ADDRESS="${LITTLE_ORBIT_PROXY_ADDRESS:-192.168.50.6}"
readonly PUBLISHED_PORT="${LITTLE_ORBIT_GATEWAY_PORT:-8180}"
readonly CHAIN_A="LITTLE_ORBIT_GATEWAY_A"
readonly CHAIN_B="LITTLE_ORBIT_GATEWAY_B"

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
  iptables -A "${chain}" -p tcp -s "${PROXY_ADDRESS}" \
    -m conntrack --ctorigdst "${EXPECTED_ADDRESS}" --ctorigdstport "${PUBLISHED_PORT}" \
    -j ACCEPT
  iptables -A "${chain}" -p tcp \
    -m conntrack --ctorigdst "${EXPECTED_ADDRESS}" --ctorigdstport "${PUBLISHED_PORT}" \
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

require_target
replace_owned_chain
verify_no_ipv6_listener
printf '{"outcome":"configured","source":"%s","port":%s}\n' \
  "${PROXY_ADDRESS}" "${PUBLISHED_PORT}"
