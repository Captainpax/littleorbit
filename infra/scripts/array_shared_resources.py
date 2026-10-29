"""Pure shared-node admission; raw kernel observations need separate provenance."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any

from array_recovery_profile import fields, positive_int, require
from array_serving_resources import AGGREGATE_MEMORY, MIN_HOST_HEADROOM, aware_utc


def nonnegative(value: Any, label: str) -> int:
    require(type(value) is int and value >= 0, label)
    return value


def orbit_parent(value: Any, online_cpus: int, host_swap: int) -> dict[str, Any]:
    """Admit only the Orbit parent; shared daemons and DMS belong elsewhere."""
    parent = fields(value, {"path", "cpuPeriodUs", "cpuQuotaUs", "memoryMaxBytes",
        "swapAccountingSupported", "memorySwapMaxBytes", "controllers"}, "Orbit parent")
    path = parent["path"]
    require(type(path) is str and path.startswith("/") and path != "/"
            and ".." not in path.split("/"), "Invalid Orbit parent path")
    period = positive_int(parent["cpuPeriodUs"], "CPU period")
    quota = positive_int(parent["cpuQuotaUs"], "CPU quota")
    require(Decimal(quota) / Decimal(period) == min(8, online_cpus), "Orbit CPU cap differs")
    require(type(parent["memoryMaxBytes"]) is int
            and parent["memoryMaxBytes"] == AGGREGATE_MEMORY, "Orbit memory cap differs")
    controllers = parent["controllers"]
    require(type(controllers) is list and all(type(c) is str for c in controllers)
            and len(set(controllers)) == len(controllers)
            and {"cpu", "memory", "pids"} <= set(controllers), "Controllers unavailable")
    validate_swap_capability(parent, host_swap)
    return dict(parent)


def validate_swap_capability(parent: dict[str, Any], host_swap: int) -> None:
    """An absent kernel controller is never a fabricated zero-limit reading."""
    supported, limit = parent["swapAccountingSupported"], parent["memorySwapMaxBytes"]
    require(type(supported) is bool, "Swap capability unknown")
    if supported:
        require(type(limit) is int and limit == 0, "Orbit swap cap differs")
    else:
        require(limit is None and host_swap == 0,
                "Unavailable swap accounting requires no host swap")


def validate_shared_host(value: Any, boot_id: str, now: datetime) -> dict[str, Any]:
    """Account for remaining growth without charging existing RSS twice."""
    observation = fields(value, {"schema", "bootId", "observedAt", "onlineCpus",
        "memTotalBytes", "memAvailableBytes", "swapTotalBytes", "daemonBudgetBytes",
        "daemonCurrentBytes", "dmsReservationBytes", "dmsCurrentBytes",
        "orbitCurrentBytes", "orbitParent"}, "shared resource observation")
    require(observation["schema"] == "LITTLE_ORBIT_SHARED_NODE_RESOURCE_OBSERVATION_V2",
            "Shared resource schema differs")
    require(observation["bootId"] == boot_id, "Resource boot differs")
    require(now.tzinfo is not None and now.utcoffset() is not None, "Aware clock required")
    require(0 <= (now - aware_utc(observation["observedAt"])).total_seconds() <= 60,
            "Resource observation stale")
    online = positive_int(observation["onlineCpus"], "online CPU count")
    total = positive_int(observation["memTotalBytes"], "total memory")
    available = nonnegative(observation["memAvailableBytes"], "available memory")
    host_swap = nonnegative(observation["swapTotalBytes"], "host swap")
    require(host_swap == 0 and available <= total, "Host memory or swap differs")
    daemon_budget = positive_int(observation["daemonBudgetBytes"], "daemon budget")
    dms_budget = nonnegative(observation["dmsReservationBytes"], "DMS reservation")
    budgets = (AGGREGATE_MEMORY, daemon_budget, dms_budget)
    currents = tuple(nonnegative(observation[key], "current resource usage") for key in
                     ("orbitCurrentBytes", "daemonCurrentBytes", "dmsCurrentBytes"))
    require(all(used <= budget for used, budget in zip(currents, budgets, strict=True)),
            "Current workload exceeds admitted budget")
    require(sum(budgets) + MIN_HOST_HEADROOM <= total, "Reserved memory overcommitted")
    remaining = sum(budgets) - sum(currents)
    require(available >= remaining + MIN_HOST_HEADROOM, "Insufficient remaining RAM headroom")
    parent = orbit_parent(observation["orbitParent"], online, host_swap)
    return {"orbitParent": parent, "remainingGrowthBytes": remaining,
            "hostHeadroomBytes": MIN_HOST_HEADROOM, "daemonBudgetBytes": daemon_budget,
            "dmsReservationBytes": dms_budget,
            "swapAccounting": "enforced_zero" if parent["swapAccountingSupported"]
            else "kernel_unavailable_host_swap_disabled",
            "runtimeAccepted": False}
