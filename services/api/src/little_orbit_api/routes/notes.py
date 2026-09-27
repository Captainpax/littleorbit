"""Authenticated WebSocket note synchronization with idempotent acknowledgements."""

import asyncio
from datetime import timedelta
from typing import cast
from uuid import UUID

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Request,
    WebSocket,
    WebSocketDisconnect,
    status,
)
from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..activity_service import record_activity
from ..client_compatibility import (
    CLIENT_HEADER,
    VERSION_CODE_HEADER,
    enforced_version_floor,
    supplied_version_code,
    update_required,
)
from ..clock import SystemClock
from ..couple_access import active_member, lock_couple
from ..database import SessionFactory, session_scope
from ..dependencies import current_account
from ..domain.notes import InvalidEdit
from ..interaction_models import NoteMetadataOperation
from ..interaction_schemas import (
    NoteArchiveRequest,
    NoteCreateRequest,
    NoteHistoryEntry,
    NoteResponse,
    NoteTitleRequest,
)
from ..models import (
    Account,
    CoupleMember,
    Note,
    NoteOperation,
)
from ..note_edit_service import NoteAccessRevoked, NoteEditMessage, apply_note_edit
from ..notes_hub import NoteConnectionHub
from ..notification_hub import NotificationConnectionHub
from ..notification_service import enqueue_note_edit_event
from ..socket_auth import SocketIdentity, authenticate_socket, socket_session_active

router = APIRouter(tags=["notes"])
CREATE_RECOVERY_WINDOW = timedelta(minutes=5)


async def _authorized_snapshot(account_id: UUID, note_id: UUID) -> dict[str, object] | None:
    async with SessionFactory() as db:
        note = await db.scalar(
            select(Note)
            .join(CoupleMember, Note.couple_id == CoupleMember.couple_id)
            .where(
                CoupleMember.account_id == account_id,
                CoupleMember.left_at.is_(None),
                Note.id == note_id,
                Note.archived_at.is_(None),
            )
        )
        if note is None:
            return None
        return {
            "type": "note.snapshot",
            "revision": note.revision,
            "body": note.body,
        }


def _note_response(note: Note) -> NoteResponse:
    return NoteResponse(
        id=note.id,
        title=note.title,
        body=note.body,
        revision=note.revision,
        metadata_revision=note.metadata_revision,
        updated_at=note.updated_at,
        archived_at=note.archived_at,
        purge_after=note.purge_after,
    )


async def _recent_equivalent(
    session: AsyncSession, couple_id: UUID, payload: NoteCreateRequest
) -> Note | None:
    """Recover a just-saved document when a client lost its local create identity."""

    cutoff = SystemClock().now() - CREATE_RECOVERY_WINDOW
    result = await session.scalar(
        select(Note)
        .where(
            Note.couple_id == couple_id,
            Note.archived_at.is_(None),
            Note.title == payload.title,
            Note.body == payload.body,
            Note.updated_at >= cutoff,
        )
        .order_by(Note.updated_at.desc(), Note.id)
        .limit(1)
    )
    return cast(Note | None, result)


@router.get("/v1/notes", response_model=list[NoteResponse])
async def list_notes(
    actor: Account = Depends(current_account),
    session: AsyncSession = Depends(session_scope),
) -> list[NoteResponse]:
    """List current note snapshots for offline caching."""

    member = await active_member(session, actor.id)
    notes = list(
        await session.scalars(
            select(Note)
            .where(Note.couple_id == member.couple_id, Note.archived_at.is_(None))
            .order_by(Note.updated_at.desc())
        )
    )
    return [_note_response(note) for note in notes]


@router.post("/v1/notes", response_model=NoteResponse, status_code=status.HTTP_201_CREATED)
async def create_note(
    payload: NoteCreateRequest,
    request: Request,
    actor: Account = Depends(current_account),
    session: AsyncSession = Depends(session_scope),
) -> NoteResponse:
    """Create one note idempotently for an offline retry."""

    member = await active_member(session, actor.id)
    await lock_couple(session, member.couple_id)
    prior = await session.scalar(
        select(Note).where(Note.creation_operation_id == payload.operation_id)
    )
    if prior is not None:
        if prior.couple_id != member.couple_id:
            raise HTTPException(status.HTTP_409_CONFLICT, "Operation ID was already used")
        return _note_response(prior)
    now = SystemClock().now()
    equivalent = await _recent_equivalent(session, member.couple_id, payload)
    if equivalent is not None:
        return _note_response(equivalent)
    note = Note(
        creation_operation_id=payload.operation_id,
        couple_id=member.couple_id,
        title=payload.title,
        body=payload.body,
        revision=0,
        created_at=now,
        updated_at=now,
    )
    session.add(note)
    await session.flush()
    await record_activity(
        session, member.couple_id, actor.id, "note_created",
        f"note:create:{payload.operation_id}", target_type="note",
        target_id=note.id, target_title=note.title,
    )
    notify_account = await enqueue_note_edit_event(
        session,
        member.couple_id,
        actor.id,
        note.id,
        partner_viewing=False,
    )
    await session.commit()
    if notify_account is not None:
        notifications = cast(
            NotificationConnectionHub,
            request.app.state.notification_connections,
        )
        await notifications.available(notify_account)
    return _note_response(note)


@router.get("/v1/notes/archived", response_model=list[NoteResponse])
async def list_archived_notes(
    actor: Account = Depends(current_account),
    session: AsyncSession = Depends(session_scope),
) -> list[NoteResponse]:
    """List notes still within their seven-day undo window."""

    member = await active_member(session, actor.id)
    notes = list(
        await session.scalars(
            select(Note)
            .where(
                Note.couple_id == member.couple_id,
                Note.archived_at.is_not(None),
                Note.purge_after > SystemClock().now(),
            )
            .order_by(Note.archived_at.desc())
        )
    )
    return [_note_response(note) for note in notes]


@router.patch("/v1/notes/{note_id}", response_model=NoteResponse)
async def rename_note(
    note_id: UUID,
    payload: NoteTitleRequest,
    actor: Account = Depends(current_account),
    session: AsyncSession = Depends(session_scope),
) -> NoteResponse:
    """Rename an active note without disturbing body OT revisions."""

    member = await active_member(session, actor.id)
    note, prior = await _locked_note_metadata(
        session, note_id, member, payload.operation_id
    )
    if prior is not None:
        return NoteResponse.model_validate(prior.result)
    _expect_metadata_revision(note, payload.expected_metadata_revision)
    if note.archived_at is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, "Note is archived")
    note.title = payload.title
    return await _finish_metadata(session, note, actor.id, payload.operation_id)


@router.post("/v1/notes/{note_id}/archive", response_model=NoteResponse)
async def archive_note(
    note_id: UUID,
    payload: NoteArchiveRequest,
    actor: Account = Depends(current_account),
    session: AsyncSession = Depends(session_scope),
) -> NoteResponse:
    """Archive an active note and schedule it for purge after seven days."""

    member = await active_member(session, actor.id)
    note, prior = await _locked_note_metadata(
        session, note_id, member, payload.operation_id
    )
    if prior is not None:
        return NoteResponse.model_validate(prior.result)
    _expect_metadata_revision(note, payload.expected_metadata_revision)
    if note.archived_at is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, "Note is already archived")
    now = SystemClock().now()
    note.archived_at = now
    note.purge_after = now + timedelta(days=7)
    return await _finish_metadata(session, note, actor.id, payload.operation_id)


@router.post("/v1/notes/{note_id}/restore", response_model=NoteResponse)
async def restore_note(
    note_id: UUID,
    payload: NoteArchiveRequest,
    actor: Account = Depends(current_account),
    session: AsyncSession = Depends(session_scope),
) -> NoteResponse:
    """Restore an archived note while its undo window remains open."""

    member = await active_member(session, actor.id)
    note, prior = await _locked_note_metadata(
        session, note_id, member, payload.operation_id
    )
    if prior is not None:
        return NoteResponse.model_validate(prior.result)
    _expect_metadata_revision(note, payload.expected_metadata_revision)
    if note.archived_at is None or (
        note.purge_after is not None and note.purge_after <= SystemClock().now()
    ):
        raise HTTPException(status.HTTP_409_CONFLICT, "Note cannot be restored")
    note.archived_at = None
    note.purge_after = None
    return await _finish_metadata(session, note, actor.id, payload.operation_id)


async def _locked_note_metadata(
    session: AsyncSession,
    note_id: UUID,
    member: CoupleMember,
    operation_id: UUID,
) -> tuple[Note, NoteMetadataOperation | None]:
    """Authorize first, then lock one note and read an idempotent prior result."""

    await lock_couple(session, member.couple_id)
    note = await session.scalar(
        select(Note)
        .where(Note.id == note_id, Note.couple_id == member.couple_id)
        .with_for_update()
    )
    if note is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Note is unavailable")
    prior = await session.scalar(
        select(NoteMetadataOperation).where(
            NoteMetadataOperation.note_id == note.id,
            NoteMetadataOperation.operation_id == operation_id,
        )
    )
    return note, prior


def _expect_metadata_revision(note: Note, expected: int) -> None:
    if note.metadata_revision != expected:
        raise HTTPException(status.HTTP_409_CONFLICT, "Note metadata changed; refresh")


async def _finish_metadata(
    session: AsyncSession, note: Note, actor_id: UUID, operation_id: UUID
) -> NoteResponse:
    """Advance metadata once and persist the exact retry response."""

    note.metadata_revision += 1
    note.updated_at = SystemClock().now()
    result = _note_response(note)
    session.add(
        NoteMetadataOperation(
            note_id=note.id,
            operation_id=operation_id,
            actor_id=actor_id,
            resulting_revision=note.metadata_revision,
            result=result.model_dump(mode="json"),
            applied_at=note.updated_at,
        )
    )
    await session.commit()
    return result


@router.get("/v1/notes/{note_id}/history", response_model=list[NoteHistoryEntry])
async def note_history(
    note_id: UUID,
    actor: Account = Depends(current_account),
    session: AsyncSession = Depends(session_scope),
) -> list[NoteHistoryEntry]:
    """Return ordered operations only after current couple authorization."""

    member = await active_member(session, actor.id)
    note = await session.scalar(
        select(Note).where(Note.id == note_id, Note.couple_id == member.couple_id)
    )
    if note is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Note is unavailable")
    operations = list(
        await session.scalars(
            select(NoteOperation)
            .where(NoteOperation.note_id == note_id)
            .order_by(NoteOperation.resulting_revision)
        )
    )
    return [
        NoteHistoryEntry(
            operation_id=item.operation_id,
            actor_id=item.actor_id,
            base_revision=item.base_revision,
            resulting_revision=item.resulting_revision,
            edit=item.edit,
            applied_at=item.applied_at,
        )
        for item in operations
    ]


async def disconnect_couple_notes(couple_id: UUID, hub: NoteConnectionHub) -> None:
    """Close active sockets after unpairing so sharing stops immediately."""

    async with SessionFactory() as db:
        note_ids = list(await db.scalars(select(Note.id).where(Note.couple_id == couple_id)))
    await hub.disconnect(note_ids)


@router.websocket("/v1/notes/{note_id}")
async def note_socket(websocket: WebSocket, note_id: UUID) -> None:
    """Authenticate, authorize, then synchronize retry-safe note operations."""

    if not await _compatible_socket(websocket):
        return
    identity, snapshot = await _authorized_socket(websocket, note_id)
    if identity is None or snapshot is None:
        await websocket.close(code=4401)
        return
    await websocket.accept()
    hub = cast(NoteConnectionHub, websocket.app.state.note_connections)
    hub.add(note_id, websocket, identity.account_id)
    if not await socket_session_active(identity):
        hub.remove(note_id, websocket)
        await websocket.close(code=4401)
        return
    live_snapshot = await _authorized_snapshot(identity.account_id, note_id)
    if live_snapshot is None:
        hub.remove(note_id, websocket)
        await websocket.close(code=4403)
        return
    await websocket.send_json(live_snapshot)
    await hub.broadcast(note_id, {"type": "note.presence", "editors": hub.count(note_id)})
    await _run_note_socket(websocket, note_id, identity, hub)


async def _compatible_socket(websocket: WebSocket) -> bool:
    """Apply the version floor before authentication or relationship lookup."""

    async with SessionFactory() as db:
        floor = await enforced_version_floor(db, SystemClock().now())
    version_code = supplied_version_code(
        websocket.headers.get(CLIENT_HEADER), websocket.headers.get(VERSION_CODE_HEADER)
    )
    if update_required(version_code, floor):
        await websocket.close(code=4426, reason="client_update_required")
        return False
    return True


async def _authorized_socket(
    websocket: WebSocket, note_id: UUID
) -> tuple[SocketIdentity | None, dict[str, object] | None]:
    """Resolve authentication and note authorization without revealing existence."""

    identity = await authenticate_socket(websocket.headers.get("authorization", ""))
    snapshot = (
        await _authorized_snapshot(identity.account_id, note_id) if identity else None
    )
    return identity, snapshot


async def _run_note_socket(
    websocket: WebSocket,
    note_id: UUID,
    identity: SocketIdentity,
    hub: NoteConnectionHub,
) -> None:
    """Receive validated operations until disconnect or authorization revocation."""

    try:
        while True:
            try:
                payload = await asyncio.wait_for(websocket.receive_json(), timeout=30)
                if not await _socket_note_active(identity, note_id):
                    await websocket.close(code=4401)
                    return
                message = NoteEditMessage.model_validate(payload)
                result = await apply_note_edit(
                    note_id,
                    identity.account_id,
                    message,
                    session_token_hash=identity.token_hash,
                    partner_viewing=hub.has_other_account(note_id, identity.account_id),
                )
            except TimeoutError:
                if not await _socket_note_active(identity, note_id):
                    await websocket.close(code=4401)
                    return
                continue
            except NoteAccessRevoked:
                await websocket.close(code=4403)
                return
            except (ValidationError, InvalidEdit) as exc:
                result = {"type": "note.error", "message": str(exc)}
            notify_account = result.pop("_notify_account_id", None)
            await hub.broadcast(note_id, result)
            if isinstance(notify_account, str):
                notifications = cast(
                    NotificationConnectionHub,
                    websocket.app.state.notification_connections,
                )
                await notifications.available(UUID(notify_account))
    except WebSocketDisconnect:
        pass
    finally:
        hub.remove(note_id, websocket)
        await hub.broadcast(note_id, {"type": "note.presence", "editors": hub.count(note_id)})


async def _socket_note_active(identity: SocketIdentity, note_id: UUID) -> bool:
    if not await socket_session_active(identity):
        return False
    return await _authorized_snapshot(identity.account_id, note_id) is not None
