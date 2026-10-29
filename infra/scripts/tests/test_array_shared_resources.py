"""Shared-daemon budgets must not invent unsupported swap controls."""

from copy import deepcopy
from datetime import datetime, timezone

import pytest

from array_shared_resources import validate_shared_host

GIB = 1024**3
NOW = datetime(2026, 10, 29, tzinfo=timezone.utc)


def observation() -> dict:
    return {"schema": "LITTLE_ORBIT_SHARED_NODE_RESOURCE_OBSERVATION_V2",
        "bootId": "fixture-boot", "observedAt": NOW.isoformat(), "onlineCpus": 16,
        "memTotalBytes": 64 * GIB, "memAvailableBytes": 60 * GIB, "swapTotalBytes": 0,
        "daemonBudgetBytes": 2 * GIB, "daemonCurrentBytes": GIB,
        "dmsReservationBytes": 8 * GIB, "dmsCurrentBytes": 0, "orbitCurrentBytes": 0,
        "orbitParent": {"path": "/little-orbit", "cpuPeriodUs": 100000,
            "cpuQuotaUs": 800000, "memoryMaxBytes": 26 * GIB,
            "swapAccountingSupported": False, "memorySwapMaxBytes": None,
            "controllers": ["cpu", "memory", "pids"]}}


def test_unavailable_swap_accounting_is_honest_when_host_has_no_swap() -> None:
    result = validate_shared_host(observation(), "fixture-boot", NOW)
    assert result["swapAccounting"] == "kernel_unavailable_host_swap_disabled"
    assert result["orbitParent"]["memorySwapMaxBytes"] is None
    assert result["runtimeAccepted"] is False


def test_existing_usage_is_not_double_reserved() -> None:
    row = observation()
    row.update(orbitCurrentBytes=20 * GIB, dmsCurrentBytes=4 * GIB,
               memAvailableBytes=19 * GIB)
    result = validate_shared_host(row, "fixture-boot", NOW)
    assert result["remainingGrowthBytes"] == 11 * GIB


@pytest.mark.parametrize("field,value", [
    ("daemonCurrentBytes", 3 * GIB), ("dmsCurrentBytes", 9 * GIB),
    ("orbitCurrentBytes", 27 * GIB), ("swapTotalBytes", GIB),
    ("memAvailableBytes", 8 * GIB), ("dmsReservationBytes", 40 * GIB),
    ("bootId", "other-boot"), ("observedAt", "2026-10-28T00:00:00+00:00"),
])
def test_shortfall_overcommit_or_stale_observation_refuses(field: str, value: object) -> None:
    row = observation()
    row[field] = value
    with pytest.raises(ValueError):
        validate_shared_host(row, "fixture-boot", NOW)


def test_claiming_swap_limit_support_requires_actual_zero_limit() -> None:
    row = observation()
    row["orbitParent"]["swapAccountingSupported"] = True
    with pytest.raises(ValueError):
        validate_shared_host(row, "fixture-boot", NOW)
    row["orbitParent"]["memorySwapMaxBytes"] = 0
    assert validate_shared_host(row, "fixture-boot", NOW)["swapAccounting"] == "enforced_zero"


def test_boolean_zero_does_not_masquerade_as_numeric_controller_limit() -> None:
    row = observation()
    row["orbitParent"].update(swapAccountingSupported=True, memorySwapMaxBytes=False)
    with pytest.raises(ValueError):
        validate_shared_host(row, "fixture-boot", NOW)


def test_small_cpu_host_uses_its_real_cpu_count_and_inputs_remain_unchanged() -> None:
    row = observation()
    row["onlineCpus"] = 4
    row["orbitParent"]["cpuQuotaUs"] = 400000
    original = deepcopy(row)
    assert validate_shared_host(row, "fixture-boot", NOW)["orbitParent"]["cpuQuotaUs"] == 400000
    assert row == original
