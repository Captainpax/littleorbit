"""Content-free PostgreSQL identity and privilege migration evidence."""

from __future__ import annotations

from copy import deepcopy
from typing import Any, cast


OWNER_ROLE = "little_orbit"
SERVICE_ROLES = (
    "little_orbit_api",
    "little_orbit_worker",
    "little_orbit_media",
    "little_orbit_backup",
)
EXPECTED_ROLES = (OWNER_ROLE, *SERVICE_ROLES)
RELATION_PRIVILEGES = {
    "DELETE", "INSERT", "MAINTAIN", "REFERENCES", "SELECT", "TRIGGER", "TRUNCATE",
    "UPDATE",
}
SEQUENCE_PRIVILEGES = {"SELECT", "UPDATE", "USAGE"}
MEDIA_PRIVILEGES = {
    "activity_events": {"INSERT", "SELECT"},
    "attachment_jobs": {"SELECT", "UPDATE"},
    "attachment_storage_state": {"SELECT", "UPDATE"},
    "couples": {"SELECT", "UPDATE"},
    "note_attachments": {"SELECT", "UPDATE"},
}
RELATION_KINDS = {"table", "partitioned-table", "view", "materialized-view", "foreign-table"}


DATABASE_INVENTORY_SQL = r"""
WITH table_counts AS (
    SELECT tablename,
           ((xpath(
               '/row/count/text()',
               query_to_xml(
                   format('SELECT count(*) AS count FROM %I.%I', schemaname, tablename),
                   false,
                   true,
                   ''
               )
           ))[1]::text)::bigint AS row_count
      FROM pg_tables
     WHERE schemaname = 'public'
), counts AS (
    SELECT COALESCE(
               jsonb_object_agg(tablename, row_count ORDER BY tablename),
               '{}'::jsonb
           ) AS value
      FROM table_counts
), heads AS (
    SELECT COALESCE(jsonb_agg(version_num ORDER BY version_num), '[]'::jsonb) AS value
      FROM alembic_version
), roles AS (
    SELECT COALESCE(jsonb_agg(jsonb_build_object(
               'name', rolname,
               'login', rolcanlogin,
               'superuser', rolsuper,
               'create_db', rolcreatedb,
               'create_role', rolcreaterole,
               'inherit', rolinherit,
               'replication', rolreplication,
               'bypass_rls', rolbypassrls,
               'connection_limit', rolconnlimit,
               'password_set', rolpassword IS NOT NULL,
               'password_kind', CASE
                   WHEN rolpassword LIKE 'SCRAM-SHA-256$%' THEN 'scram-sha-256'
                   WHEN rolpassword IS NULL THEN 'absent'
                   ELSE 'other'
               END,
               'password_expiry_set', rolvaliduntil IS NOT NULL
                                      AND rolvaliduntil <> 'infinity'::timestamptz,
               'configuration_set', EXISTS (
                   SELECT 1
                     FROM pg_db_role_setting role_setting
                    WHERE role_setting.setrole = pg_authid.oid
                      AND COALESCE(cardinality(role_setting.setconfig), 0) <> 0
               )
           ) ORDER BY rolname), '[]'::jsonb) AS value
      FROM pg_authid
     WHERE rolname !~ '^pg_'
), memberships AS (
    SELECT COALESCE(jsonb_agg(jsonb_build_object(
               'role', parent.rolname,
               'member', child.rolname,
               'grantor', grantor.rolname,
               'admin', membership.admin_option,
               'inherit', membership.inherit_option,
               'set', membership.set_option
           ) ORDER BY parent.rolname, child.rolname, grantor.rolname), '[]'::jsonb) AS value
      FROM pg_auth_members membership
      JOIN pg_roles parent ON parent.oid = membership.roleid
      JOIN pg_roles child ON child.oid = membership.member
      JOIN pg_roles grantor ON grantor.oid = membership.grantor
     WHERE parent.rolname !~ '^pg_' OR child.rolname !~ '^pg_'
), database_security AS (
    SELECT jsonb_build_object(
               'owner', pg_get_userbyid(database_value.datdba),
               'acl', COALESCE((
                   SELECT jsonb_agg(jsonb_build_object(
                              'grantee', CASE WHEN item.grantee = 0 THEN 'PUBLIC'
                                              ELSE pg_get_userbyid(item.grantee) END,
                              'grantor', pg_get_userbyid(item.grantor),
                              'privilege', item.privilege_type,
                              'grantable', item.is_grantable
                          ) ORDER BY item.grantee, item.privilege_type, item.grantor)
                     FROM aclexplode(COALESCE(
                              database_value.datacl,
                              acldefault('d', database_value.datdba)
                          )) item
               ), '[]'::jsonb)
           ) AS value
      FROM pg_database database_value
     WHERE database_value.datname = current_database()
), schema_security AS (
    SELECT jsonb_build_object(
               'owner', pg_get_userbyid(namespace_value.nspowner),
               'acl', COALESCE((
                   SELECT jsonb_agg(jsonb_build_object(
                              'grantee', CASE WHEN item.grantee = 0 THEN 'PUBLIC'
                                              ELSE pg_get_userbyid(item.grantee) END,
                              'grantor', pg_get_userbyid(item.grantor),
                              'privilege', item.privilege_type,
                              'grantable', item.is_grantable
                          ) ORDER BY item.grantee, item.privilege_type, item.grantor)
                     FROM aclexplode(COALESCE(
                              namespace_value.nspacl,
                              acldefault('n', namespace_value.nspowner)
                          )) item
               ), '[]'::jsonb)
           ) AS value
      FROM pg_namespace namespace_value
     WHERE namespace_value.nspname = 'public'
), objects AS (
    SELECT COALESCE(jsonb_agg(jsonb_build_object(
               'name', object_value.relname,
               'kind', CASE object_value.relkind
                   WHEN 'r' THEN 'table'
                   WHEN 'p' THEN 'partitioned-table'
                   WHEN 'v' THEN 'view'
                   WHEN 'm' THEN 'materialized-view'
                   WHEN 'f' THEN 'foreign-table'
                   WHEN 'S' THEN 'sequence'
               END,
               'owner', pg_get_userbyid(object_value.relowner),
               'acl', COALESCE((
                   SELECT jsonb_agg(jsonb_build_object(
                              'grantee', CASE WHEN item.grantee = 0 THEN 'PUBLIC'
                                              ELSE pg_get_userbyid(item.grantee) END,
                              'grantor', pg_get_userbyid(item.grantor),
                              'privilege', item.privilege_type,
                              'grantable', item.is_grantable
                          ) ORDER BY item.grantee, item.privilege_type, item.grantor)
                     FROM aclexplode(COALESCE(
                              object_value.relacl,
                              acldefault(
                                  CASE WHEN object_value.relkind = 'S' THEN 'S'::"char"
                                       ELSE 'r'::"char" END,
                                  object_value.relowner
                              )
                          )) item
               ), '[]'::jsonb)
           ) ORDER BY object_value.relkind, object_value.relname), '[]'::jsonb) AS value
      FROM pg_class object_value
      JOIN pg_namespace namespace_value ON namespace_value.oid = object_value.relnamespace
     WHERE namespace_value.nspname = 'public'
       AND object_value.relkind IN ('r', 'p', 'v', 'm', 'f', 'S')
), defaults AS (
    SELECT COALESCE(jsonb_agg(jsonb_build_object(
               'owner', pg_get_userbyid(default_value.defaclrole),
               'kind', CASE default_value.defaclobjtype
                   WHEN 'r' THEN 'relation'
                   WHEN 'S' THEN 'sequence'
               END,
               'acl', COALESCE((
                   SELECT jsonb_agg(jsonb_build_object(
                              'grantee', CASE WHEN item.grantee = 0 THEN 'PUBLIC'
                                              ELSE pg_get_userbyid(item.grantee) END,
                              'grantor', pg_get_userbyid(item.grantor),
                              'privilege', item.privilege_type,
                              'grantable', item.is_grantable
                          ) ORDER BY item.grantee, item.privilege_type, item.grantor)
                     FROM aclexplode(default_value.defaclacl) item
               ), '[]'::jsonb)
           ) ORDER BY pg_get_userbyid(default_value.defaclrole), default_value.defaclobjtype),
           '[]'::jsonb) AS value
      FROM pg_default_acl default_value
      JOIN pg_namespace namespace_value ON namespace_value.oid = default_value.defaclnamespace
     WHERE namespace_value.nspname = 'public'
       AND default_value.defaclobjtype IN ('r', 'S')
), security AS (
    SELECT jsonb_build_object(
               'roles', roles.value,
               'memberships', memberships.value,
               'database', database_security.value,
               'schema', schema_security.value,
               'objects', objects.value,
               'defaults', defaults.value
           ) AS value
      FROM roles CROSS JOIN memberships CROSS JOIN database_security
      CROSS JOIN schema_security CROSS JOIN objects CROSS JOIN defaults
)
SELECT jsonb_build_object(
           'tables', counts.value,
           'schema_heads', heads.value,
           'security', security.value
       )
  FROM counts CROSS JOIN heads CROSS JOIN security;
""".strip()


def _acl_key(value: dict[str, object]) -> tuple[str, str, str, bool]:
    return (
        cast(str, value["grantee"]), cast(str, value["privilege"]),
        cast(str, value["grantor"]), cast(bool, value["grantable"]),
    )


def _parse_acl(value: object) -> list[dict[str, object]]:
    if not isinstance(value, list):
        raise RuntimeError("database security ACL is invalid")
    expected = {"grantee", "grantor", "privilege", "grantable"}
    parsed: list[dict[str, object]] = []
    for item in value:
        if not isinstance(item, dict) or set(item) != expected:
            raise RuntimeError("database security ACL is invalid")
        if not all(isinstance(item[key], str) and item[key] for key in expected - {"grantable"}):
            raise RuntimeError("database security ACL is invalid")
        if not isinstance(item["grantable"], bool):
            raise RuntimeError("database security ACL is invalid")
        parsed.append(dict(item))
    result = sorted(parsed, key=_acl_key)
    if len(result) != len({_acl_key(item) for item in result}):
        raise RuntimeError("database security ACL contains duplicates")
    return result


def _parse_roles(value: object) -> list[dict[str, object]]:
    expected = {
        "name", "login", "superuser", "create_db", "create_role", "inherit",
        "replication", "bypass_rls", "connection_limit", "password_set",
        "password_kind", "password_expiry_set", "configuration_set",
    }
    if not isinstance(value, list):
        raise RuntimeError("database role inventory is invalid")
    roles: list[dict[str, object]] = []
    for role in value:
        if not isinstance(role, dict) or set(role) != expected:
            raise RuntimeError("database role inventory is invalid")
        if not isinstance(role["name"], str) or not isinstance(role["connection_limit"], int):
            raise RuntimeError("database role inventory is invalid")
        bools = expected - {"name", "connection_limit", "password_kind"}
        if not all(isinstance(role[key], bool) for key in bools):
            raise RuntimeError("database role inventory is invalid")
        if role["password_kind"] not in {"absent", "scram-sha-256", "other"}:
            raise RuntimeError("database role inventory is invalid")
        roles.append(dict(role))
    return sorted(roles, key=lambda role: cast(str, role["name"]))


def _parse_memberships(value: object) -> list[dict[str, object]]:
    expected = {"role", "member", "grantor", "admin", "inherit", "set"}
    if not isinstance(value, list):
        raise RuntimeError("database membership inventory is invalid")
    result: list[dict[str, object]] = []
    for item in value:
        if not isinstance(item, dict) or set(item) != expected:
            raise RuntimeError("database membership inventory is invalid")
        if not all(isinstance(item[key], str) and item[key] for key in {"role", "member", "grantor"}):
            raise RuntimeError("database membership inventory is invalid")
        if not all(isinstance(item[key], bool) for key in {"admin", "inherit", "set"}):
            raise RuntimeError("database membership inventory is invalid")
        result.append(dict(item))
    return sorted(result, key=lambda item: (
        cast(str, item["role"]), cast(str, item["member"]), cast(str, item["grantor"]),
    ))


def _parse_owned_acl(value: object) -> dict[str, object]:
    if not isinstance(value, dict) or set(value) != {"owner", "acl"}:
        raise RuntimeError("database owned ACL inventory is invalid")
    if not isinstance(value["owner"], str) or not value["owner"]:
        raise RuntimeError("database owned ACL inventory is invalid")
    return {"owner": value["owner"], "acl": _parse_acl(value["acl"])}


def _parse_objects(value: object) -> list[dict[str, object]]:
    if not isinstance(value, list):
        raise RuntimeError("database object security inventory is invalid")
    result: list[dict[str, object]] = []
    for item in value:
        if not isinstance(item, dict) or set(item) != {"name", "kind", "owner", "acl"}:
            raise RuntimeError("database object security inventory is invalid")
        if not all(isinstance(item[key], str) and item[key] for key in {"name", "kind", "owner"}):
            raise RuntimeError("database object security inventory is invalid")
        if item["kind"] not in RELATION_KINDS | {"sequence"}:
            raise RuntimeError("database object security inventory is invalid")
        result.append({**item, "acl": _parse_acl(item["acl"])})
    return sorted(result, key=lambda item: (cast(str, item["kind"]), cast(str, item["name"])))


def _parse_defaults(value: object) -> list[dict[str, object]]:
    if not isinstance(value, list):
        raise RuntimeError("database default ACL inventory is invalid")
    result: list[dict[str, object]] = []
    for item in value:
        if not isinstance(item, dict) or set(item) != {"owner", "kind", "acl"}:
            raise RuntimeError("database default ACL inventory is invalid")
        if item["owner"] == "" or item["kind"] not in {"relation", "sequence"}:
            raise RuntimeError("database default ACL inventory is invalid")
        result.append({**item, "acl": _parse_acl(item["acl"])})
    return sorted(result, key=lambda item: (cast(str, item["owner"]), cast(str, item["kind"])))


def parse_security(value: object) -> dict[str, object]:
    """Validate and canonicalize content-free database security evidence."""

    expected = {"roles", "memberships", "database", "schema", "objects", "defaults"}
    if not isinstance(value, dict) or set(value) != expected:
        raise RuntimeError("database security inventory is invalid")
    return {
        "roles": _parse_roles(value["roles"]),
        "memberships": _parse_memberships(value["memberships"]),
        "database": _parse_owned_acl(value["database"]),
        "schema": _parse_owned_acl(value["schema"]),
        "objects": _parse_objects(value["objects"]),
        "defaults": _parse_defaults(value["defaults"]),
    }


def _expected_role(name: str) -> dict[str, object]:
    owner = name == OWNER_ROLE
    return {
        "name": name, "login": True, "superuser": owner, "create_db": owner,
        "create_role": owner, "inherit": True, "replication": owner,
        "bypass_rls": owner, "connection_limit": -1, "password_set": True,
        "password_kind": "scram-sha-256", "password_expiry_set": False,
        "configuration_set": False,
    }


def _expected_acl(
    owner_privileges: set[str], service_privileges: dict[str, set[str]],
    public_privileges: set[str] | None = None,
) -> set[tuple[str, str, bool]]:
    values = {(OWNER_ROLE, privilege, False) for privilege in owner_privileges}
    for role, privileges in service_privileges.items():
        values.update((role, privilege, False) for privilege in privileges)
    values.update(("PUBLIC", privilege, False) for privilege in public_privileges or set())
    return values


def _actual_acl(value: object) -> set[tuple[str, str, bool]]:
    return {
        (cast(str, item["grantee"]), cast(str, item["privilege"]), cast(bool, item["grantable"]))
        for item in cast(list[dict[str, object]], value)
    }


def _assert_acl(value: object, expected: set[tuple[str, str, bool]]) -> None:
    acl = cast(list[dict[str, object]], value)
    actual = _actual_acl(acl)
    if len(acl) != len(actual) or actual != expected:
        raise RuntimeError("database privilege policy is not exact")
    if any(item["grantor"] not in {OWNER_ROLE, "pg_database_owner"} for item in acl):
        raise RuntimeError("database privilege grantor policy is not exact")


def _generic_relation_acl() -> set[tuple[str, str, bool]]:
    return _expected_acl(RELATION_PRIVILEGES, {
        "little_orbit_api": {"DELETE", "INSERT", "SELECT", "UPDATE"},
        "little_orbit_worker": {"DELETE", "INSERT", "SELECT", "UPDATE"},
        "little_orbit_backup": {"SELECT"},
    })


def _generic_sequence_acl() -> set[tuple[str, str, bool]]:
    return _expected_acl(SEQUENCE_PRIVILEGES, {
        "little_orbit_api": {"SELECT", "USAGE"},
        "little_orbit_worker": {"SELECT", "USAGE"},
        "little_orbit_backup": {"SELECT"},
    })


def _default_relation_acl() -> set[tuple[str, str, bool]]:
    return _expected_acl(set(), {
        "little_orbit_api": {"DELETE", "INSERT", "SELECT", "UPDATE"},
        "little_orbit_worker": {"DELETE", "INSERT", "SELECT", "UPDATE"},
        "little_orbit_backup": {"SELECT"},
    })


def _default_sequence_acl() -> set[tuple[str, str, bool]]:
    return _expected_acl(set(), {
        "little_orbit_api": {"SELECT", "USAGE"},
        "little_orbit_worker": {"SELECT", "USAGE"},
        "little_orbit_backup": {"SELECT"},
    })


def _assert_roles(security: dict[str, object]) -> None:
    expected = sorted((_expected_role(name) for name in EXPECTED_ROLES), key=lambda role: cast(str, role["name"]))
    if security["roles"] != expected or security["memberships"] != []:
        raise RuntimeError("database role policy is not exact")


def _assert_cluster_acls(security: dict[str, object]) -> None:
    database = cast(dict[str, object], security["database"])
    schema = cast(dict[str, object], security["schema"])
    connect = {role: {"CONNECT"} for role in SERVICE_ROLES}
    usage = {role: {"USAGE"} for role in SERVICE_ROLES}
    if database["owner"] != OWNER_ROLE or schema["owner"] != "pg_database_owner":
        raise RuntimeError("database ownership policy is not exact")
    _assert_acl(database["acl"], _expected_acl(
        {"CONNECT", "CREATE", "TEMPORARY"}, connect, {"CONNECT"},
    ))
    schema_owner_acl = _expected_acl(set(), usage, {"USAGE"})
    schema_owner_acl.update({("pg_database_owner", privilege, False) for privilege in {"CREATE", "USAGE"}})
    _assert_acl(schema["acl"], schema_owner_acl)


def _assert_object(item: dict[str, object]) -> None:
    if item["owner"] != OWNER_ROLE:
        raise RuntimeError("database object ownership policy is not exact")
    name = cast(str, item["name"])
    if item["kind"] == "sequence":
        expected = _generic_sequence_acl()
    else:
        expected = _generic_relation_acl()
        expected.update(("little_orbit_media", privilege, False) for privilege in MEDIA_PRIVILEGES.get(name, set()))
    _assert_acl(item["acl"], expected)


def _assert_defaults(security: dict[str, object]) -> None:
    defaults = cast(list[dict[str, object]], security["defaults"])
    if [(item["owner"], item["kind"]) for item in defaults] != [
        (OWNER_ROLE, "relation"), (OWNER_ROLE, "sequence"),
    ]:
        raise RuntimeError("database default privilege policy is not exact")
    _assert_acl(defaults[0]["acl"], _default_relation_acl())
    _assert_acl(defaults[1]["acl"], _default_sequence_acl())


def assert_static_policy(security: dict[str, object]) -> None:
    """Fail closed unless the database has exactly the reviewed least privileges."""

    _assert_roles(security)
    _assert_cluster_acls(security)
    for item in cast(list[dict[str, object]], security["objects"]):
        _assert_object(item)
    _assert_defaults(security)


def without_object(security: dict[str, object], name: str) -> dict[str, object]:
    """Return comparable evidence without one reviewed migration-created object."""

    result = deepcopy(security)
    objects = cast(list[dict[str, object]], result["objects"])
    result["objects"] = [item for item in objects if item["name"] != name]
    return result


def parse_database_inventory(raw: str) -> dict[str, object]:
    """Validate the database inventory and its static security policy."""

    import json

    parsed: Any = json.loads(raw)
    if not isinstance(parsed, dict) or set(parsed) != {"tables", "schema_heads", "security"}:
        raise RuntimeError("database inventory is not an object")
    tables = parsed["tables"]
    heads = parsed["schema_heads"]
    if not isinstance(tables, dict) or not all(
        isinstance(name, str) and isinstance(count, int) and count >= 0
        for name, count in tables.items()
    ):
        raise RuntimeError("database table counts are invalid")
    if not isinstance(heads, list) or not heads or not all(isinstance(head, str) and head for head in heads):
        raise RuntimeError("database schema head is invalid")
    security = parse_security(parsed["security"])
    assert_static_policy(security)
    return {"tables": dict(sorted(tables.items())), "schema_heads": sorted(heads), "security": security}
