"""Command-line contract for the fixed Little Orbit direct migration."""

from __future__ import annotations

import argparse
from collections.abc import Mapping
from pathlib import Path

LEGACY_HOST = "192.168.50.182"
UNRAID_HOST = "192.168.50.14"
UNRAID_SSH_PORT = 23
UNRAID_STACK = "/mnt/cache/little-orbit-deploy/repo/infra/scripts/unraid-stack.sh"
CONFIRMATIONS = {
    "forward": "forward-.182-to-.14-users-offline",
    "rollback": "post-write-rollback-.14-to-.182-users-offline",
    "recover-forward": "recover-interrupted-forward-.14-state",
    "recover-rollback": "recover-interrupted-rollback-.182-state",
}


class MigrationFailure(RuntimeError):
    """A migration failure with content-free recovery evidence."""

    def __init__(self, recovery: Mapping[str, str]) -> None:
        super().__init__("direct migration failed; inspect structured recovery status")
        self.recovery = dict(recovery)


def parser(description: str | None) -> argparse.ArgumentParser:
    """Build a direction-explicit, archive-free migration interface."""

    value = argparse.ArgumentParser(description=description)
    value.add_argument("--direction", required=True, choices=tuple(CONFIRMATIONS))
    value.add_argument("--local-host", default=LEGACY_HOST)
    value.add_argument("--unraid-host", required=True)
    value.add_argument("--unraid-user", default="root")
    value.add_argument("--unraid-port", type=int, default=UNRAID_SSH_PORT)
    value.add_argument("--ssh-identity", type=Path, required=True)
    value.add_argument("--known-hosts", type=Path, required=True)
    value.add_argument("--backup-identity", type=Path)
    value.add_argument("--unraid-stack", default=UNRAID_STACK)
    value.add_argument("--local-env", type=Path, default=Path(".env"))
    value.add_argument("--local-release-root", type=Path, default=Path("data/releases"))
    value.add_argument("--rollback-data-root", type=Path)
    value.add_argument("--confirm", required=True)
    return value
