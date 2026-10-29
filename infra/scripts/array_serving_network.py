"""Pure DNAT/egress scope model. This module never emits or applies host commands."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
import ipaddress
from typing import Any

from array_recovery_profile import fields, require
from array_serving_resources import aware_utc

HOST = "192.168.50.14"
NPM = "192.168.50.6"
CADDY = "10.253.14.2"
API = "10.253.14.3"
CONTEXT_HOSTS = frozenset({"www.un.org", "www.opm.gov", "science.nasa.gov",
                           "www.loc.gov", "www.si.edu"})
EGRESS = {
    "context-fetcher": {"network": "context-egress", "subnet": "10.253.14.16/29",
        "gateway": "10.253.14.17", "ip": "10.253.14.18", "bridge": "lo-ctx-egress"},
    "worker": {"network": "worker-mail-egress", "subnet": "10.253.14.24/29",
        "gateway": "10.253.14.25", "ip": "10.253.14.26", "bridge": "lo-mail-egress"},
}
DNS_OPTIONS = ["ndots:0", "timeout:2", "attempts:1"]
OWNED_CHAINS = ("LO_ORBIT_IN8", "LO_ORBIT_FWD8", "LO_ORBIT_OUT8", "LO_ORBIT_PUB9",
                "LO_ORBIT_EGRESS9", "LO_ORBIT_DNAT9", "LO_ORBIT_SNAT9")


def ipv4(value: Any) -> ipaddress.IPv4Address:
    require(type(value) is str, "IPv4 address missing")
    try:
        result = ipaddress.ip_address(value)
    except ValueError:
        require(False, "IPv4 address invalid")
        raise AssertionError("unreachable") from None
    require(isinstance(result, ipaddress.IPv4Address), "IPv6 egress not admitted")
    return result


def validate_resolvers(value: Any) -> tuple[str, ...]:
    """No host-loopback forwarding: upstream DNS must cross the owned bridge hook."""
    require(type(value) is list and 1 <= len(value) <= 2, "DNS resolver count invalid")
    require(all(type(item) is str for item in value), "DNS resolver type invalid")
    require(len(set(value)) == len(value), "DNS resolvers repeated")
    for item in value:
        address = ipv4(item)
        require(not (address.is_loopback or address.is_link_local or address.is_multicast
                     or address.is_unspecified or address.is_reserved), "DNS resolver not routable")
        require(item not in {HOST, NPM, CADDY, API}, "DNS resolver aliases recovery endpoint")
    return tuple(value)


@dataclass(frozen=True)
class AddressLease:
    """An exact-name DNS result, not permission to use arbitrary URLs or ports."""

    hostname: str
    addresses: tuple[str, ...]
    observed_at: datetime
    ttl_seconds: int

    def valid(self, now: datetime) -> bool:
        return 0 <= (now - self.observed_at).total_seconds() < self.ttl_seconds


def address_lease(value: Any, hostname: str, public_only: bool) -> AddressLease:
    record = fields(value, {"hostname", "addresses", "observedAt", "ttlSeconds"}, "DNS lease")
    require(record["hostname"] == hostname, "DNS name differs from admitted configuration")
    addresses = record["addresses"]
    require(type(addresses) is list and 1 <= len(addresses) <= 32
            and all(type(item) is str for item in addresses), "DNS address count/type invalid")
    require(len(set(addresses)) == len(addresses), "DNS addresses repeated")
    for item in addresses:
        address = ipv4(item)
        require(not (address.is_loopback or address.is_link_local or address.is_multicast
                     or address.is_unspecified or address.is_reserved), "DNS destination unsafe")
        require(not public_only or address.is_global, "Context DNS destination not public")
        require(item not in {HOST, NPM, CADDY, API}, "SMTP destination aliases protected endpoint")
    ttl = record["ttlSeconds"]
    require(type(ttl) is int and 1 <= ttl <= 300, "DNS lease TTL outside policy")
    return AddressLease(hostname, tuple(addresses), aware_utc(record["observedAt"]), ttl)


def merge_address_leases(hostname: str, values: tuple[AddressLease, ...],
                         now: datetime, public_only: bool) -> tuple[AddressLease, ...]:
    """Retain each verified IP only until its own observed DNS lifetime expires."""
    current = aware_utc(now.isoformat())
    retained: dict[str, AddressLease] = {}
    for value in values:
        checked = address_lease({"hostname": value.hostname,
            "addresses": list(value.addresses), "observedAt": value.observed_at.isoformat(),
            "ttlSeconds": value.ttl_seconds}, hostname, public_only)
        if not checked.valid(current):
            continue
        for address in checked.addresses:
            previous = retained.get(address)
            expiry = checked.observed_at + timedelta(seconds=checked.ttl_seconds)
            if previous is None or expiry > previous.observed_at + timedelta(seconds=previous.ttl_seconds):
                retained[address] = AddressLease(hostname, (address,),
                    checked.observed_at, checked.ttl_seconds)
    require(len(retained) <= 32, "Merged DNS addresses exceed bounded policy")
    return tuple(retained[address] for address in sorted(retained))


@dataclass(frozen=True, repr=False)
class EgressPolicy:
    """Private SMTP metadata stays in memory; no repr/export or credential fields."""

    resolvers: tuple[str, ...]
    context: tuple[AddressLease, ...]
    smtp: AddressLease
    smtp_port: int

    def permits(self, role: str, bridge: str, source: str, destination: str,
                protocol: str, port: int, now: datetime) -> bool:
        """Model NEW outbound tuples only; reverse ESTABLISHED must join this tuple."""
        if not scope_matches(role, bridge, source):
            return False
        if type(port) is not int or protocol not in {"tcp", "udp"}:
            return False
        if destination in self.resolvers and port == 53:
            return True
        if protocol != "tcp":
            return False
        return self.permits_target(role, destination, port, now)

    def permits_target(self, role: str, destination: str, port: int, now: datetime) -> bool:
        if role == "worker":
            return port == self.smtp_port and self.smtp.valid(now) and destination in self.smtp.addresses
        if role == "context-fetcher":
            return port == 443 and any(lease.valid(now) and destination in lease.addresses
                                       for lease in self.context)
        return False


def scope_matches(role: str, bridge: str, source: str) -> bool:
    scope = EGRESS.get(role)
    return scope is not None and bridge == scope["bridge"] and source == scope["ip"]


def egress_policy(resolvers: Any, context: Any, smtp_hostname: str,
                  smtp_port: int, smtp_starttls: bool, smtp: Any) -> EgressPolicy:
    """Inputs come from protected config and bounded DNS proofs, never guessed defaults."""
    require(type(smtp_hostname) is str and 0 < len(smtp_hostname) <= 253
            and not any(char.isspace() for char in smtp_hostname), "SMTP hostname invalid")
    require(type(smtp_port) is int and 1 <= smtp_port <= 65535 and smtp_port != 465,
            "SMTP port not compatible with admitted STARTTLS adapter")
    require(smtp_starttls is True, "Serving SMTP requires verified STARTTLS")
    records = fields(context, set(CONTEXT_HOSTS), "context DNS names")
    leases = tuple(address_lease(records[name], name, True) for name in sorted(CONTEXT_HOSTS))
    return EgressPolicy(validate_resolvers(resolvers), leases,
                         address_lease(smtp, smtp_hostname, False), smtp_port)


def ingress_dnat(source: str, destination: str, protocol: str, port: int) -> tuple[str, int] | None:
    """No SNAT: unchanged Caddy must still see NPM as its direct peer."""
    if (source, destination, protocol, port) == (NPM, HOST, "tcp", 8180):
        return CADDY, 8180
    return None


def planned_hooks() -> dict[str, Any]:
    """Describe authority boundaries, not a firewall script or native proof."""
    return {"schema": "LITTLE_ORBIT_OWNED_NETWORK_SCOPE_V2", "chains": list(OWNED_CHAINS),
        "sets": [], "kernelExpiry": "iptables-time-UTC-datestop",
        "forwardHook": "FORWARD", "natIngressHook": "PREROUTING",
        "natEgressHook": "POSTROUTING", "ingressSnat": False,
        "snatAddress": HOST, "caddyNpmReturnRoute": f"{NPM}/32 via 10.253.14.1",
        "dockerFirewallManagementUnchanged": True, "otherRulesOrPoliciesMayChange": False,
        "runtimeActionsAvailable": [], "runtimeAccepted": False}
