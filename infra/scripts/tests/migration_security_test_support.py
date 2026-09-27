"""Canonical PostgreSQL security evidence shared by migration tests."""

from __future__ import annotations

import importlib.util
from pathlib import Path
import sys
from typing import Any


SCRIPT_DIR = Path(__file__).resolve().parents[1]


def load_script(name: str) -> Any:
    spec = importlib.util.spec_from_file_location(name.removesuffix(".py"), SCRIPT_DIR / name)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


SECURITY = load_script("migration_security.py")
INVENTORY = load_script("migration_inventory.py")


def _acl(
    values: set[tuple[str, str, bool]],
    *,
    schema: bool = False,
) -> list[dict[str, object]]:
    result = []
    for grantee, privilege, grantable in sorted(values):
        grantor = "pg_database_owner" if schema and grantee == "pg_database_owner" else "little_orbit"
        result.append({
            "grantee": grantee,
            "grantor": grantor,
            "privilege": privilege,
            "grantable": grantable,
        })
    return result


def _reviewed_security(*, queue: bool = False) -> dict[str, object]:
    connect = {role: {"CONNECT"} for role in SECURITY.SERVICE_ROLES}
    usage = {role: {"USAGE"} for role in SECURITY.SERVICE_ROLES}
    database_acl = SECURITY._expected_acl(
        {"CONNECT", "CREATE", "TEMPORARY"}, connect, {"CONNECT"},
    )
    schema_acl = SECURITY._expected_acl(set(), usage, {"USAGE"})
    schema_acl.update({
        ("pg_database_owner", "CREATE", False),
        ("pg_database_owner", "USAGE", False),
    })
    objects = [{
        "name": "activity_events",
        "kind": "table",
        "owner": "little_orbit",
        "acl": _acl(SECURITY._generic_relation_acl() | {
            ("little_orbit_media", "INSERT", False),
            ("little_orbit_media", "SELECT", False),
        }),
    }]
    if queue:
        objects.append({
            "name": "ai_work_queue", "kind": "table", "owner": "little_orbit",
            "acl": _acl(SECURITY._generic_relation_acl()),
        })
    return {
        "roles": sorted(
            (SECURITY._expected_role(name) for name in SECURITY.EXPECTED_ROLES),
            key=lambda role: role["name"],
        ),
        "memberships": [],
        "database": {"owner": "little_orbit", "acl": _acl(database_acl)},
        "schema": {
            "owner": "pg_database_owner", "acl": _acl(schema_acl, schema=True),
        },
        "objects": sorted(objects, key=lambda item: (item["kind"], item["name"])),
        "defaults": [
            {
                "owner": "little_orbit", "kind": "relation",
                "acl": _acl(SECURITY._default_relation_acl()),
            },
            {
                "owner": "little_orbit", "kind": "sequence",
                "acl": _acl(SECURITY._default_sequence_acl()),
            },
        ],
    }


def _database(head: str = "0031", *, queue: bool = False) -> dict[str, object]:
    tables = {"activity_events": 4}
    if queue:
        tables["ai_work_queue"] = 0
    return {
        "tables": tables,
        "schema_heads": [head],
        "security": _reviewed_security(queue=queue),
    }


def _migration_inventory(database: dict[str, object]) -> object:
    return INVENTORY.MigrationInventory(
        database=database,
        attachments=INVENTORY.AttachmentInventory(0, 0, "0" * 64),
        releases={},
    )
