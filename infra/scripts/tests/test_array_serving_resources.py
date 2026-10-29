"""Exact approved ceilings and fresh raw controller-value models, not host proof."""

from copy import deepcopy
from datetime import datetime, timedelta, timezone
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import array_serving_resources as resources
from array_recovery_profile import ProfileError

NOW = datetime(2026, 10, 22, 20, tzinfo=timezone.utc)
BOOT = "synthetic-boot-not-host-proof"


def observation() -> dict:
    return {"observedAt": NOW.isoformat(), "bootId": BOOT, "onlineCpus": 16,
        "memAvailableBytes": 40 * resources.GIB, "swapTotalBytes": 0, "cgroupVersion": 2,
        "controllers": ["cpu", "memory", "pids"], "aggregate": {"path": "/little-orbit-recovery",
            "cpuPeriodUs": 100000, "cpuQuotaUs": 800000,
            "memoryMaxBytes": 26 * resources.GIB, "memorySwapMaxBytes": 0}}


class ResourceTests(unittest.TestCase):
    def test_exact_table_has_26g_parent_and_4g_clamav(self) -> None:
        values = resources.approved_resources()
        resources.validate_resources(values)
        self.assertEqual(values["clamav"]["memoryBytes"], 4 * resources.GIB)
        self.assertEqual(sum(row["memoryBytes"] for row in values.values()), 22784 * resources.MIB)
        self.assertEqual(sum(row["pids"] for row in values.values()), 1536)
        self.assertFalse(resources.validate_host_resources(observation(), BOOT, NOW)["runtimeAccepted"])

    def test_smaller_native_cpu_host_gets_smaller_aggregate(self) -> None:
        host = observation()
        host["onlineCpus"] = 4
        with self.assertRaises(ProfileError):
            resources.validate_host_resources(host, BOOT, NOW)
        host["aggregate"]["cpuQuotaUs"] = 400000
        resources.validate_host_resources(host, BOOT, NOW)

    def test_fresh_ram_swap_controller_boot_and_age_refuse_unknown(self) -> None:
        changes = [("memAvailableBytes", 33 * resources.GIB), ("swapTotalBytes", 1),
                   ("controllers", ["cpu", "memory"]), ("bootId", "other"),
                   ("onlineCpus", True), ("cgroupVersion", True)]
        for key, value in changes:
            host = observation()
            host[key] = value
            with self.subTest(key=key), self.assertRaises(ProfileError):
                resources.validate_host_resources(host, BOOT, NOW)
        with self.assertRaises(ProfileError):
            resources.validate_host_resources(observation(), BOOT, NOW + timedelta(seconds=61))

    def test_no_mutable_default_or_boolean_quantity(self) -> None:
        values = resources.approved_resources()
        values["worker"]["pids"] = True
        with self.assertRaises(ProfileError):
            resources.validate_resources(values)
        self.assertEqual(resources.approved_resources()["worker"]["pids"], 256)
        host = deepcopy(observation())
        host["aggregate"]["memorySwapMaxBytes"] = True
        with self.assertRaises(ProfileError):
            resources.validate_host_resources(host, BOOT, NOW)


if __name__ == "__main__":
    unittest.main()
