"""Small in-process fixed-window limiter for single-instance registration defense.

Production deployments should move counters to PostgreSQL if API replicas are added.
The public behavior remains neutral regardless of whether a limit is exceeded.
"""

from collections import defaultdict, deque
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from threading import Lock


@dataclass
class FixedWindowLimiter:
    """Thread-safe bounded event limiter keyed by a privacy-minimized digest."""

    limit: int
    window: timedelta
    _events: dict[str, deque[datetime]] = field(default_factory=lambda: defaultdict(deque))
    _lock: Lock = field(default_factory=Lock)

    def allow(self, key: str, now: datetime) -> bool:
        """Record an allowed event, or return false when the key is limited."""

        cutoff = now - self.window
        with self._lock:
            events = self._events[key]
            while events and events[0] <= cutoff:
                events.popleft()
            if len(events) >= self.limit:
                return False
            events.append(now)
            return True
