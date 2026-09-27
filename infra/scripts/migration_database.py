"""PostgreSQL guards and archive-free streaming for direct migration."""

from __future__ import annotations

import argparse
from collections.abc import Callable, Mapping
from dataclasses import dataclass
import shlex

import migration_inventory as inventory


@dataclass(frozen=True)
class Runtime:
    run_stack: Callable[..., str]
    stack_command: Callable[..., list[str]]
    stack_environment: Callable[..., Mapping[str, str] | None]
    pipe: Callable[..., None]


def psql(sql: str) -> str:
    return (
        'psql --username="$POSTGRES_USER" --dbname="$POSTGRES_DB" --quiet '
        f"--tuples-only --no-align --set=ON_ERROR_STOP=1 --command={shlex.quote(sql)}"
    )


def assert_empty_database(
    runtime: Runtime, args: argparse.Namespace, location: str,
) -> None:
    """Require an object-free application catalog in the fresh destination."""

    sql = (
        "DO $migration$ BEGIN "
        "IF EXISTS (SELECT 1 FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace "
        "WHERE n.nspname NOT IN ('pg_catalog','information_schema') "
        "AND n.nspname NOT LIKE 'pg_toast%' AND n.nspname NOT LIKE 'pg_temp%') "
        "OR EXISTS (SELECT 1 FROM pg_proc p JOIN pg_namespace n ON n.oid=p.pronamespace "
        "WHERE n.nspname NOT IN ('pg_catalog','information_schema') "
        "AND n.nspname NOT LIKE 'pg_toast%' AND n.nspname NOT LIKE 'pg_temp%') "
        "OR EXISTS (SELECT 1 FROM pg_namespace WHERE nspname NOT IN "
        "('pg_catalog','information_schema','public') AND nspname NOT LIKE 'pg_toast%' "
        "AND nspname NOT LIKE 'pg_temp%') THEN "
        "RAISE EXCEPTION 'destination database is not fresh'; END IF; "
        "END $migration$; SELECT 'empty';"
    )
    observed = runtime.run_stack(
        args, location, "exec", "-T", "postgres", "sh", "-ec", psql(sql),
        capture=True,
    )
    if observed.strip() != "empty":
        raise RuntimeError("destination database did not prove empty")


def prepare_database(runtime: Runtime, args: argparse.Namespace, location: str) -> None:
    runtime.run_stack(args, location, "up", "-d", "--wait", "postgres")
    assert_empty_database(runtime, args, location)
    runtime.run_stack(args, location, "run", "--rm", "-T", "database-bootstrap")


def assert_no_unexpected_database_sessions(
    runtime: Runtime, args: argparse.Namespace, location: str,
) -> None:
    sql = (
        "SELECT count(*) FROM pg_stat_activity WHERE datname=current_database() "
        "AND pid<>pg_backend_pid() AND backend_type='client backend';"
    )
    observed = runtime.run_stack(
        args, location, "exec", "-T", "postgres", "sh", "-ec", psql(sql),
        capture=True,
    )
    if observed.strip() != "0":
        raise RuntimeError("frozen source database still has an unexpected client session")


def database_inventory(
    runtime: Runtime, args: argparse.Namespace, location: str,
) -> dict[str, object]:
    raw = runtime.run_stack(
        args, location, "exec", "-T", "postgres", "sh", "-ec",
        psql(inventory.DATABASE_INVENTORY_SQL), capture=True,
    )
    return inventory.parse_database_inventory(raw)


def stream_database(
    runtime: Runtime, args: argparse.Namespace, source: str, destination: str,
) -> None:
    """Pipe a complete custom dump into one fresh database transaction."""

    dump = (
        'pg_dump --format=custom --no-owner --username="$POSTGRES_USER" '
        '"$POSTGRES_DB"'
    )
    restore = (
        "pg_restore --clean --if-exists --no-owner --single-transaction "
        '--exit-on-error --username="$POSTGRES_USER" --dbname="$POSTGRES_DB"'
    )
    producer = runtime.stack_command(
        args, source, "exec", "-T", "postgres", "sh", "-ec", dump,
    )
    consumer = runtime.stack_command(
        args, destination, "exec", "-T", "postgres", "sh", "-ec", restore,
    )
    runtime.pipe(
        producer, consumer,
        source_env=runtime.stack_environment(args, source),
        destination_env=runtime.stack_environment(args, destination),
    )
    runtime.run_stack(args, destination, "run", "--rm", "-T", "database-bootstrap")
    runtime.run_stack(
        args, destination, "run", "--rm", "-T", "--no-deps", "migrate",
    )
    runtime.run_stack(
        args, destination, "run", "--rm", "-T", "--no-deps", "database-grants",
    )
