"""Restart and verify the exact writer set frozen by a migration."""

from __future__ import annotations

import argparse
from collections.abc import Callable
import json
import time


StackRunner = Callable[..., str]
ContainerStarter = Callable[[argparse.Namespace, str, tuple[str, ...]], None]


def _parse_compose_status(raw: str) -> list[dict[str, object]]:
    """Accept Compose's array and newline-delimited JSON status formats."""

    try:
        parsed = json.loads(raw)
        if isinstance(parsed, dict):
            return [parsed]
        if isinstance(parsed, list) and all(isinstance(item, dict) for item in parsed):
            return parsed
    except json.JSONDecodeError:
        pass
    values: list[dict[str, object]] = []
    for line in raw.splitlines():
        parsed_line = json.loads(line)
        if not isinstance(parsed_line, dict):
            raise RuntimeError("Compose returned invalid writer status")
        values.append(parsed_line)
    return values


def _writer_container_ids(
    rows: list[dict[str, object]], writers: tuple[str, ...],
) -> tuple[str, ...]:
    """Resolve one existing Compose container ID for every frozen writer."""

    by_service: dict[str, str] = {}
    for row in rows:
        service = str(row.get("Service", ""))
        container_id = str(row.get("ID", ""))
        if service not in writers or service in by_service:
            raise RuntimeError("Compose returned ambiguous writer containers")
        if not 12 <= len(container_id) <= 64 or any(
            character not in "0123456789abcdef" for character in container_id.lower()
        ):
            raise RuntimeError("Compose returned an invalid writer container")
        by_service[service] = container_id
    if set(by_service) != set(writers):
        raise RuntimeError("an existing source writer container is missing")
    return tuple(by_service[service] for service in writers)


def restart_source_writers(
    args: argparse.Namespace,
    source: str,
    writers: tuple[str, ...],
    run_stack: StackRunner,
    start_containers: ContainerStarter,
) -> None:
    """Restart exactly the preflight writers and prove each is ready."""

    existing = run_stack(
        args, source, "ps", "--all", "--format", "json", *writers,
        capture=True,
    )
    start_containers(args, source, _writer_container_ids(
        _parse_compose_status(existing), writers,
    ))
    deadline = time.monotonic() + 300
    while True:
        raw = run_stack(
            args, source, "ps", "--format", "json", *writers, capture=True,
        )
        rows = _parse_compose_status(raw)
        ready = {
            str(row.get("Service"))
            for row in rows
            if str(row.get("State", "")).lower() == "running"
            and str(row.get("Health", "")).lower() in {"", "healthy"}
        }
        if ready == set(writers):
            return
        if time.monotonic() >= deadline:
            raise RuntimeError("source writers did not return healthy after recovery")
        time.sleep(2)
