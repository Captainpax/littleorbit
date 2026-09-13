"""Focused tests for transient, account-scoped note presence."""

from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from little_orbit_api.notes_hub import NoteConnectionHub


@pytest.mark.asyncio
async def test_presence_counts_accounts_instead_of_sockets() -> None:
    """Two sockets from one device must still represent one editor."""

    hub = NoteConnectionHub()
    note_id = uuid4()
    first_account = uuid4()
    second_account = uuid4()
    observer = AsyncMock()
    writer = AsyncMock()
    partner = AsyncMock()

    hub.add(note_id, observer, first_account)
    hub.add(note_id, writer, first_account)
    hub.add(note_id, partner, second_account)

    assert hub.count(note_id) == 2
    assert hub.has_other_account(note_id, first_account)
    hub.remove(note_id, partner)
    assert hub.count(note_id) == 1
    assert not hub.has_other_account(note_id, first_account)


@pytest.mark.asyncio
async def test_disconnect_closes_each_socket_and_clears_presence() -> None:
    """Unpairing closes every socket even when one account opened several."""

    hub = NoteConnectionHub()
    note_id = uuid4()
    account_id = uuid4()
    sockets = [AsyncMock(), AsyncMock()]
    for socket in sockets:
        hub.add(note_id, socket, account_id)

    await hub.disconnect([note_id])

    assert hub.count(note_id) == 0
    for socket in sockets:
        socket.close.assert_awaited_once_with(code=4403)
