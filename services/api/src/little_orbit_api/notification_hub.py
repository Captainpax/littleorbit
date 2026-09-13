"""Process-local foreground notification hints for the single API instance."""

from collections import defaultdict
from uuid import UUID

from fastapi import WebSocket


class NotificationConnectionHub:
    """Own authenticated foreground sockets without persisting content."""

    def __init__(self) -> None:
        self._connections: dict[UUID, set[WebSocket]] = defaultdict(set)

    def add(self, account_id: UUID, socket: WebSocket) -> None:
        """Register one authenticated foreground installation."""

        self._connections[account_id].add(socket)

    def remove(self, account_id: UUID, socket: WebSocket) -> None:
        """Remove a disconnected installation and empty account set."""

        connections = self._connections.get(account_id)
        if connections is None:
            return
        connections.discard(socket)
        if not connections:
            self._connections.pop(account_id, None)

    async def available(self, account_id: UUID) -> None:
        """Send a content-free hint and prune sockets that disappeared."""

        for socket in tuple(self._connections.get(account_id, set())):
            try:
                await socket.send_json({"type": "notification.available"})
            except RuntimeError:
                self.remove(account_id, socket)
