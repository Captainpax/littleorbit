"""No network calls: exact forward/SNAT scope, DNS expiry and no model egress."""

from datetime import datetime, timedelta, timezone
import importlib.util
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import array_serving_network as network
from array_recovery_profile import ProfileError

NOW = datetime(2026, 10, 22, 20, tzinfo=timezone.utc)


def lease(hostname: str, address: str = "8.8.8.8") -> dict:
    return {"hostname": hostname, "addresses": [address], "observedAt": NOW.isoformat(),
            "ttlSeconds": 60}


def policy() -> network.EgressPolicy:
    return network.egress_policy(["192.168.50.1"],
        {name: lease(name) for name in network.CONTEXT_HOSTS}, "smtp.example.invalid", 587, True,
        lease("smtp.example.invalid", "192.168.50.20"))


class NetworkTests(unittest.TestCase):
    def test_exact_ingress_dnat_preserves_npm_source(self) -> None:
        self.assertEqual(network.ingress_dnat(network.NPM, network.HOST, "tcp", 8180),
                         (network.CADDY, 8180))
        for source, destination, protocol, port in (("192.168.50.182", network.HOST, "tcp", 8180),
                (network.NPM, network.CADDY, "tcp", 8180), (network.NPM, network.HOST, "udp", 8180),
                (network.NPM, network.HOST, "tcp", 8000)):
            self.assertIsNone(network.ingress_dnat(source, destination, protocol, port))
        self.assertFalse(network.planned_hooks()["ingressSnat"])
        self.assertEqual(network.planned_hooks()["runtimeActionsAvailable"], [])
        self.assertTrue(network.planned_hooks()["dockerFirewallManagementUnchanged"])
        self.assertEqual(network.planned_hooks()["sets"], [])
        self.assertEqual(network.planned_hooks()["kernelExpiry"], "iptables-time-UTC-datestop")

    def test_only_exact_fetcher_https_and_worker_smtp_tuples(self) -> None:
        value = policy()
        context = network.EGRESS["context-fetcher"]
        worker = network.EGRESS["worker"]
        self.assertTrue(value.permits("context-fetcher", context["bridge"], context["ip"],
                                     "8.8.8.8", "tcp", 443, NOW))
        self.assertTrue(value.permits("worker", worker["bridge"], worker["ip"],
                                     "192.168.50.20", "tcp", 587, NOW))
        for role, scope, destination, port in (("worker", worker, "8.8.8.8", 443),
                ("context-fetcher", context, "192.168.50.20", 587),
                ("worker", worker, "192.168.50.20", 25), ("ollama", worker, "8.8.8.8", 443)):
            self.assertFalse(value.permits(role, scope["bridge"], scope["ip"], destination,
                                          "tcp", port, NOW))

    def test_source_bridge_ipv4_and_resolver_are_all_closed(self) -> None:
        value = policy()
        context = network.EGRESS["context-fetcher"]
        self.assertTrue(value.permits("context-fetcher", context["bridge"], context["ip"],
                                     "192.168.50.1", "udp", 53, NOW))
        for bridge, source, destination, port in (("foreign", context["ip"], "8.8.8.8", 443),
                (context["bridge"], "10.253.14.19", "8.8.8.8", 443),
                (context["bridge"], context["ip"], "1.1.1.1", 53),
                (context["bridge"], context["ip"], "8.8.8.8", True)):
            self.assertFalse(value.permits("context-fetcher", bridge, source, destination,
                                          "tcp", port, NOW))
        for resolvers in (["127.0.0.1"], [network.HOST], ["::1"], ["169.254.1.1"]):
            with self.subTest(resolvers=resolvers), self.assertRaises(ProfileError):
                network.validate_resolvers(resolvers)

    def test_expiry_and_dns_rebinding_fail_closed(self) -> None:
        value = policy()
        scope = network.EGRESS["context-fetcher"]
        for now in (NOW - timedelta(seconds=1), NOW + timedelta(seconds=60)):
            self.assertFalse(value.permits("context-fetcher", scope["bridge"], scope["ip"],
                                          "8.8.8.8", "tcp", 443, now))
        for address in ("127.0.0.1", "10.0.0.1", "169.254.169.254", "::ffff:127.0.0.1"):
            with self.subTest(address=address), self.assertRaises(ProfileError):
                network.address_lease(lease("www.un.org", address), "www.un.org", True)

    def test_rotating_dns_answers_keep_independent_expiry(self) -> None:
        first = network.AddressLease("www.un.org", ("8.8.8.8",), NOW, 60)
        second = network.AddressLease("www.un.org", ("1.1.1.1",), NOW + timedelta(seconds=10), 60)
        merged = network.merge_address_leases("www.un.org", (first, second),
                                               NOW + timedelta(seconds=10), True)
        self.assertEqual({row.addresses[0] for row in merged}, {"8.8.8.8", "1.1.1.1"})
        self.assertEqual(next(row for row in merged if row.addresses == ("8.8.8.8",)), first)
        later = network.merge_address_leases("www.un.org", merged,
                                              NOW + timedelta(seconds=60), True)
        self.assertEqual(later, (second,))
        self.assertEqual(network.merge_address_leases("www.un.org", merged,
                         NOW + timedelta(seconds=70), True), ())

    def test_dns_union_never_admits_future_rebound_or_excess_addresses(self) -> None:
        future = network.AddressLease("www.un.org", ("8.8.8.8",), NOW + timedelta(seconds=1), 60)
        self.assertEqual(network.merge_address_leases("www.un.org", (future,), NOW, True), ())
        for host, address in (("foreign.invalid", "8.8.8.8"), ("www.un.org", "127.0.0.1")):
            value = network.AddressLease(host, (address,), NOW, 60)
            with self.assertRaises(ProfileError):
                network.merge_address_leases("www.un.org", (value,), NOW, True)
        many = tuple(network.AddressLease("www.un.org", (f"8.8.8.{index}",), NOW, 60)
                     for index in range(1, 34))
        with self.assertRaises(ProfileError):
            network.merge_address_leases("www.un.org", many, NOW, True)
        too_long = lease("www.un.org") | {"ttlSeconds": 301}
        with self.assertRaises(ProfileError):
            network.address_lease(too_long, "www.un.org", True)

    def test_target_helper_itself_never_defaults_an_unknown_role_to_context(self) -> None:
        value = policy()
        for role in ("ollama", "media-worker", "api", "unknown", ""):
            self.assertFalse(value.permits_target(role, "8.8.8.8", 443, NOW))

    def test_catalogue_is_the_real_source_set_not_an_infrastructure_guess(self) -> None:
        path = Path(__file__).resolve().parents[3] / "services/api/src/little_orbit_api/public_context_catalog.py"
        spec = importlib.util.spec_from_file_location("actual_context_catalog", path)
        assert spec and spec.loader
        module = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = module
        spec.loader.exec_module(module)
        self.assertEqual({row.hostname for row in module.PUBLIC_CONTEXT_SOURCES}, network.CONTEXT_HOSTS)


if __name__ == "__main__":
    unittest.main()
