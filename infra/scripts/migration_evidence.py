"""Build content-free location and success evidence for direct migration."""

from __future__ import annotations

import migration_inventory as inventory


def migration_locations(direction: str) -> tuple[str, str]:
    return (
        ("local-production", "unraid")
        if direction == "forward"
        else ("unraid", "local-rollback")
    )


def success_evidence(
    *,
    direction: str,
    source: str,
    destination: str,
    before: inventory.MigrationInventory,
    after: inventory.MigrationInventory,
    legacy_host: str,
    unraid_host: str,
    rollback_project: str,
) -> dict[str, object]:
    """Return the privacy-safe proof emitted after atomic promotion."""

    return {
        "outcome": "streamed-and-matched",
        "direction": direction,
        "source": {
            "host": legacy_host if source == "local-production" else unraid_host,
            "inventory": before.serializable(),
        },
        "destination": {
            "host": unraid_host if destination == "unraid" else legacy_host,
            "project": (
                "little-orbit" if destination == "unraid" else rollback_project
            ),
            "inventory": after.serializable(),
        },
        "source_writers": "stopped",
        "inventories_match": True,
    }
