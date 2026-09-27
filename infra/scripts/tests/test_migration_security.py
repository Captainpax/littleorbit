from __future__ import annotations

from copy import deepcopy
import json
from typing import Any

import pytest

from infra.scripts.tests.migration_security_test_support import (
    INVENTORY,
    SECURITY,
    SCRIPT_DIR,
    _database,
    _migration_inventory,
    _reviewed_security,
)


def test_database_inventory_accepts_only_the_reviewed_static_policy() -> None:
    parsed = SECURITY.parse_database_inventory(json.dumps(_database()))

    assert parsed["schema_heads"] == ["0031"]
    roles = parsed["security"]["roles"]
    assert {role["name"] for role in roles} == set(SECURITY.EXPECTED_ROLES)
    assert all("rolpassword" not in role for role in roles)


@pytest.mark.parametrize(
    ("mutate", "message"),
    [
        (
            lambda value: value["roles"].append({
                **SECURITY._expected_role("little_orbit_api"), "name": "unexpected_role",
            }),
            "role policy",
        ),
        (
            lambda value: value["memberships"].append({
                "role": "pg_read_all_data", "member": "little_orbit_api",
                "grantor": "little_orbit", "admin": False, "inherit": True, "set": True,
            }),
            "role policy",
        ),
        (
            lambda value: value["objects"][0]["acl"].append({
                "grantee": "PUBLIC", "grantor": "little_orbit",
                "privilege": "SELECT", "grantable": False,
            }),
            "privilege policy",
        ),
        (
            lambda value: value["roles"][0].update({"configuration_set": True}),
            "role policy",
        ),
    ],
)
def test_static_policy_rejects_extra_authority(mutate: Any, message: str) -> None:
    security = _reviewed_security()
    mutate(security)

    with pytest.raises(RuntimeError, match=message):
        SECURITY.assert_static_policy(security)


def test_static_policy_rejects_media_access_to_the_ai_queue() -> None:
    security = _reviewed_security(queue=True)
    queue = next(item for item in security["objects"] if item["name"] == "ai_work_queue")
    queue["acl"].append({
        "grantee": "little_orbit_media", "grantor": "little_orbit",
        "privilege": "SELECT", "grantable": False,
    })

    with pytest.raises(RuntimeError, match="privilege policy"):
        SECURITY.assert_static_policy(security)


def test_forward_security_delta_allows_only_the_empty_0032_queue() -> None:
    source = _migration_inventory(_database())
    destination = _migration_inventory(_database("0032", queue=True))

    INVENTORY.assert_destination_matching(source, destination, "forward")

    destination.database["security"]["objects"][0]["acl"].append({
        "grantee": "PUBLIC", "grantor": "little_orbit",
        "privilege": "SELECT", "grantable": False,
    })
    with pytest.raises(RuntimeError, match="security inventories differ"):
        INVENTORY.assert_destination_matching(source, destination, "forward")


def test_bootstrap_normalizes_roles_memberships_and_acl_surfaces() -> None:
    content = (SCRIPT_DIR.parent / "postgres" / "bootstrap-roles.sql").read_text(encoding="utf-8")

    assert "LOGIN INHERIT NOSUPERUSER" in content
    assert "CONNECTION LIMIT -1 VALID UNTIL 'infinity'" in content
    assert "RESET ALL" in content
    assert "FROM pg_auth_members membership" in content
    assert "REVOKE ALL PRIVILEGES ON %s %I.%I" in content
    assert "ALTER DEFAULT PRIVILEGES FOR ROLE %I IN SCHEMA %I" in content
    assert "REVOKE ALL PRIVILEGES ON %s FROM %s" in content


def test_inventory_never_serializes_a_password_verifier() -> None:
    security = deepcopy(_reviewed_security())
    serialized = json.dumps(security, sort_keys=True)

    assert "SCRAM-SHA-256$" not in serialized
    assert "rolpassword" not in serialized
    assert '"password_kind": "scram-sha-256"' in serialized
