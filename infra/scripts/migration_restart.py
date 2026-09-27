"""Restart and verify the exact writer set frozen by a migration."""

from __future__ import annotations

import argparse
from collections.abc import Callable
import json
import time


StackRunner = Callable[..., str]


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


def restart_source_writers(
    args: argparse.Namespace,
    source: str,
    writers: tuple[str, ...],
    run_stack: StackRunner,
) -> None:
    """Restart exactly the preflight writers and prove each is ready."""

    run_stack(args, source, "start", *writers)
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
