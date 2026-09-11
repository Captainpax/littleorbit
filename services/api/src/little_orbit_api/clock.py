"""Deterministic clock boundary used by security and domain services."""

from datetime import UTC, datetime
from typing import Protocol


class Clock(Protocol):
    """Source of timezone-aware UTC time."""

    def now(self) -> datetime:
        """Return the current instant."""


class SystemClock:
    """Production clock backed by the operating system."""

    def now(self) -> datetime:
        """Return the current UTC instant."""

        return datetime.now(UTC)
