"""Approved recovery ceilings and pure fresh-observation checks, not an actuator."""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from typing import Any

from array_recovery_profile import cpu, fields, positive_int, require

MIB = 1024**2
GIB = 1024**3
AGGREGATE_MEMORY = 26 * GIB
MIN_HOST_HEADROOM = 8 * GIB
# Child CPU values are ceilings, not reservations: their sum may exceed parent 8.
ROLE_BOUNDS = {
    "gateway": ("0.25", 256, 64), "web": ("1", 768, 128),
    "api": ("1", 1024, 256), "postgres": ("2", 4096, 256),
    "worker": ("2", 2048, 256), "context-fetcher": ("0.5", 256, 64),
    "ollama": ("4", 8192, 256), "media-worker": ("2", 2048, 128),
    "clamav": ("1", 4096, 128),
}


def approved_resources() -> dict[str, dict[str, Any]]:
    """Return new input objects; never let a caller mutate the fixed table."""
    return {name: {"cpus": cpus, "memoryBytes": mib * MIB, "pids": pids}
            for name, (cpus, mib, pids) in ROLE_BOUNDS.items()}


def validate_resources(value: Any) -> None:
    """Require exact approved child ceilings, including ClamAV's 4 GiB."""
    resources = fields(value, set(ROLE_BOUNDS), "serving resources")
    for name, expected in approved_resources().items():
        actual = fields(resources[name], {"cpus", "memoryBytes", "pids"}, "role ceiling")
        require(cpu(actual["cpus"]) == cpu(expected["cpus"]), "Role CPU ceiling differs")
        for key in ("memoryBytes", "pids"):
            require(type(actual[key]) is int and actual[key] == expected[key],
                    "Role memory/PID ceiling differs")


def aware_utc(value: Any) -> datetime:
    """Parse only explicit instants; never renew a historical observation."""
    require(type(value) is str, "Observation time missing")
    try:
        result = datetime.fromisoformat(value)
    except ValueError:
        require(False, "Observation time invalid")
        raise AssertionError("unreachable") from None
    require(result.tzinfo is not None and result.utcoffset() is not None,
            "Observation time must be aware")
    return result.astimezone(timezone.utc)


def validate_host_resources(value: Any, boot_id: str, now: datetime) -> dict[str, Any]:
    """Check supplied raw controller values; provenance remains an external gate."""
    host = fields(value, {"observedAt", "bootId", "onlineCpus", "memAvailableBytes",
        "swapTotalBytes", "cgroupVersion", "controllers", "aggregate"}, "resource observation")
    require(host["bootId"] == boot_id, "Resource observation boot differs")
    require(now.tzinfo is not None, "Current time must be aware")
    require(0 <= (now - aware_utc(host["observedAt"])).total_seconds() <= 60,
            "Resource observation not fresh")
    online = positive_int(host["onlineCpus"], "online CPU count")
    require(type(host["memAvailableBytes"]) is int and host["memAvailableBytes"] >=
            AGGREGATE_MEMORY + MIN_HOST_HEADROOM, "Insufficient fresh RAM headroom")
    require(type(host["swapTotalBytes"]) is int and host["swapTotalBytes"] == 0,
            "Host swap must remain disabled")
    require(type(host["cgroupVersion"]) is int and host["cgroupVersion"] in (1, 2),
            "Native cgroup controller admission required")
    controllers = host["controllers"]
    require(type(controllers) is list and all(type(item) is str for item in controllers)
            and len(controllers) == len(set(controllers))
            and set(controllers) >= {"cpu", "memory", "pids"}, "Cgroup controllers unavailable")
    aggregate = validate_aggregate(host["aggregate"], online)
    return {"aggregate": aggregate, "roleMemoryBytes": sum(
        row["memoryBytes"] for row in approved_resources().values()),
        "requiredHostHeadroomBytes": MIN_HOST_HEADROOM, "runtimeAccepted": False}


def validate_aggregate(value: Any, online: int) -> dict[str, Any]:
    """The future observer must join *both* daemons and all nine CIDs to this parent."""
    parent = fields(value, {"path", "cpuPeriodUs", "cpuQuotaUs", "memoryMaxBytes",
        "memorySwapMaxBytes"}, "aggregate limits")
    require(type(parent["path"]) is str and parent["path"].startswith("/")
            and parent["path"] != "/" and ".." not in parent["path"].split("/"),
            "Owned cgroup path invalid")
    period = positive_int(parent["cpuPeriodUs"], "CPU period")
    quota = positive_int(parent["cpuQuotaUs"], "CPU quota")
    require(Decimal(quota) / Decimal(period) == min(8, online), "Aggregate CPU cap differs")
    require(type(parent["memoryMaxBytes"]) is int and
            parent["memoryMaxBytes"] == AGGREGATE_MEMORY, "Aggregate RAM cap differs")
    require(type(parent["memorySwapMaxBytes"]) is int and parent["memorySwapMaxBytes"] == 0,
            "Aggregate swap cap differs")
    return dict(parent)
