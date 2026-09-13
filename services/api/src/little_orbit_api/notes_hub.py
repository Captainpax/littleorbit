"""Process-local WebSocket coordination for the single API instance."""

from collections import defaultdict
from uuid import UUID

from fastapi import WebSocket


class NoteConnectionHub:
    """Own active note sockets without exposing mutable module state."""

    def __init__(self) -> None:
        self._connections: dict[UUID, dict[WebSocket, UUID]] = defaultdict(dict)

    def add(self, note_id: UUID, socket: WebSocket, account_id: UUID) -> None:
        """Register one already authenticated connection."""

        self._connections[note_id][socket] = account_id

    def remove(self, note_id: UUID, socket: WebSocket) -> None:
        """Remove a disconnected socket and its empty note set."""

        connections = self._connections.get(note_id)
        if connections is None:
            return
        connections.pop(socket, None)
        if not connections:
            self._connections.pop(note_id, None)

    def count(self, note_id: UUID) -> int:
        """Return transient connected-editor count without storing identity or content."""

        return len(set(self._connections.get(note_id, {}).values()))

    async def broadcast(self, note_id: UUID, payload: dict[str, object]) -> None:
        """Deliver an applied operation while pruning sockets that disappeared."""

        for socket in tuple(self._connections.get(note_id, {})):
            try:
                await socket.send_json(payload)
            except RuntimeError:
                self.remove(note_id, socket)

    async def disconnect(self, note_ids: list[UUID]) -> None:
        """Close all relationship sockets immediately after sharing ends."""

        for note_id in note_ids:
            for socket in tuple(self._connections.pop(note_id, {})):
                await socket.close(code=4403)
