"""Authenticated WebSocket note synchronization with idempotent acknowledgements."""

from typing import cast
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect, status
from pydantic import BaseModel, ConfigDict, Field, ValidationError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..client_compatibility import (
    CLIENT_HEADER,
    VERSION_CODE_HEADER,
    enforced_version_floor,
    supplied_version_code,
    update_required,
)
from ..clock import SystemClock
from ..config import get_settings
from ..couple_access import active_member, lock_couple
from ..database import SessionFactory, session_scope
from ..dependencies import current_account
from ..domain.notes import Delete, Edit, Insert, InvalidEdit, apply_edit, transform
from ..models import Account, CoupleMember, Note, NoteOperation, Session
from ..notes_hub import NoteConnectionHub
from ..schemas import NoteCreateRequest, NoteHistoryEntry, NoteResponse
from ..security import hash_token

router = APIRouter(tags=["notes"])


class NoteAccessRevoked(RuntimeError):
    """Raised when active membership ended after a socket connected."""


class NoteEditMessage(BaseModel):
    """Validated WebSocket edit envelope."""

    model_config = ConfigDict(extra="forbid")
    operation_id: UUID
    base_revision: int = Field(ge=0)
    kind: str
    position: int = Field(ge=0)
    text: str | None = Field(default=None, max_length=4000)
    length: int | None = Field(default=None, ge=1, le=4000)


async def _authenticate(token: str) -> UUID | None:
    settings = get_settings()
    digest = hash_token(token, settings.token_pepper.get_secret_value())
    async with SessionFactory() as db:
        account_id = await db.scalar(
            select(Session.account_id).where(
                Session.token_hash == digest,
                Session.revoked_at.is_(None),
                Session.expires_at > SystemClock().now(),
            )
        )
        return account_id


async def _authorized_snapshot(account_id: UUID, note_id: UUID) -> dict[str, object] | None:
    async with SessionFactory() as db:
        note = await db.scalar(
            select(Note)
            .join(CoupleMember, Note.couple_id == CoupleMember.couple_id)
            .where(
                CoupleMember.account_id == account_id,
                CoupleMember.left_at.is_(None),
                Note.id == note_id,
            )
        )
        if note is None:
            return None
        return {
            "type": "note.snapshot",
            "revision": note.revision,
            "body": note.body,
        }


def _parse_edit(message: NoteEditMessage) -> Insert | Delete:
    if message.kind == "insert" and message.text:
        return Insert(message.position, message.text)
    if message.kind == "delete" and message.length:
        return Delete(message.position, message.length)
    raise InvalidEdit("edit fields do not match kind")


def _stored_edit(edit: Edit) -> dict[str, object]:
    if isinstance(edit, Insert):
        return {"kind": "insert", "position": edit.position, "text": edit.text}
    return {"kind": "delete", "position": edit.position, "length": edit.length}


def _restore_edit(payload: dict[str, object]) -> Edit:
    kind = payload.get("kind")
    position = payload.get("position")
    if not isinstance(position, int):
        raise InvalidEdit("stored edit position is invalid")
    if kind == "insert" and isinstance(payload.get("text"), str):
        return Insert(position, str(payload["text"]))
    length = payload.get("length")
    if kind == "delete" and isinstance(length, int):
        return Delete(position, length)
    raise InvalidEdit("stored edit shape is invalid")


async def _transform_since(
    db: AsyncSession, note: Note, message: NoteEditMessage, incoming: Edit
) -> Edit | None:
    if message.base_revision == note.revision:
        return incoming
    operations = list(
        await db.scalars(
            select(NoteOperation)
            .where(
                NoteOperation.note_id == note.id,
                NoteOperation.resulting_revision > message.base_revision,
            )
            .order_by(NoteOperation.resulting_revision)
        )
    )
    if len(operations) != note.revision - message.base_revision:
        return None
    transformed = incoming
    for operation in operations:
        transformed = transform(
            transformed,
            _restore_edit(operation.edit),
            message.operation_id.int < operation.operation_id.int,
        )
    return transformed


async def _apply(note_id: UUID, account_id: UUID, message: NoteEditMessage) -> dict[str, object]:
    async with SessionFactory() as db:
        authorized = await db.scalar(
            select(CoupleMember.id)
            .join(Note, Note.couple_id == CoupleMember.couple_id)
            .where(
                CoupleMember.account_id == account_id,
                CoupleMember.left_at.is_(None),
                Note.id == note_id,
            )
        )
        if authorized is None:
            raise NoteAccessRevoked
        note = await db.scalar(select(Note).where(Note.id == note_id).with_for_update())
        existing = await db.scalar(
            select(NoteOperation).where(
                NoteOperation.note_id == note_id,
                NoteOperation.operation_id == message.operation_id,
            )
        )
        if existing:
            return _duplicate_ack(existing, note, message)
        if note is None or message.base_revision > note.revision:
            return _conflict(note)
        edit = await _transform_since(db, note, message, _parse_edit(message))
        if edit is None:
            return _conflict(note)
        note.body = _apply_non_empty_edit(note.body, edit)
        note.revision += 1
        note.updated_at = SystemClock().now()
        db.add(
            NoteOperation(
                note_id=note_id,
                operation_id=message.operation_id,
                actor_id=account_id,
                base_revision=message.base_revision,
                resulting_revision=note.revision,
                edit=_stored_edit(edit),
                applied_at=SystemClock().now(),
            )
        )
        await db.commit()
        return {
            "type": "note.ack",
            "operation_id": str(message.operation_id),
            "revision": note.revision,
            "body": note.body,
            "transformed": message.base_revision != note.revision - 1,
        }


def _duplicate_ack(
    existing: NoteOperation, note: Note | None, message: NoteEditMessage
) -> dict[str, object]:
    return {
        "type": "note.ack",
        "operation_id": str(message.operation_id),
        "revision": existing.resulting_revision,
        "body": note.body if note else "",
        "transformed": existing.base_revision != existing.resulting_revision - 1,
    }


def _conflict(note: Note | None) -> dict[str, object]:
    return {
        "type": "note.conflict",
        "revision": note.revision if note else 0,
        "body": note.body if note else "",
    }


def _apply_non_empty_edit(body: str, edit: Edit) -> str:
    if isinstance(edit, Delete) and edit.length == 0:
        return body
    return apply_edit(body, edit)


def _note_response(note: Note) -> NoteResponse:
    return NoteResponse(
        id=note.id,
        title=note.title,
        body=note.body,
        revision=note.revision,
        updated_at=note.updated_at,
    )


@router.get("/v1/notes", response_model=list[NoteResponse])
async def list_notes(
    actor: Account = Depends(current_account),
    session: AsyncSession = Depends(session_scope),
) -> list[NoteResponse]:
    """List current note snapshots for offline caching."""

    member = await active_member(session, actor.id)
    notes = list(
        await session.scalars(
            select(Note).where(Note.couple_id == member.couple_id).order_by(Note.updated_at.desc())
        )
    )
    return [_note_response(note) for note in notes]


@router.post("/v1/notes", response_model=NoteResponse, status_code=status.HTTP_201_CREATED)
async def create_note(
    payload: NoteCreateRequest,
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
    await session.commit()
    return _note_response(note)


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
    account_id, snapshot = await _authorized_socket(websocket, note_id)
    if account_id is None or snapshot is None:
        await websocket.close(code=4401)
        return
    await websocket.accept()
    hub = cast(NoteConnectionHub, websocket.app.state.note_connections)
    hub.add(note_id, websocket)
    await websocket.send_json(snapshot)
    await _run_note_socket(websocket, note_id, account_id, hub)


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
) -> tuple[UUID | None, dict[str, object] | None]:
    """Resolve authentication and note authorization without revealing existence."""

    authorization = websocket.headers.get("authorization", "")
    token = authorization[7:] if authorization.startswith("Bearer ") else ""
    account_id = await _authenticate(token) if token else None
    snapshot = await _authorized_snapshot(account_id, note_id) if account_id else None
    return account_id, snapshot


async def _run_note_socket(
    websocket: WebSocket,
    note_id: UUID,
    account_id: UUID,
    hub: NoteConnectionHub,
) -> None:
    """Receive validated operations until disconnect or authorization revocation."""

    try:
        while True:
            try:
                message = NoteEditMessage.model_validate(await websocket.receive_json())
                result = await _apply(note_id, account_id, message)
            except NoteAccessRevoked:
                await websocket.close(code=4403)
                return
            except (ValidationError, InvalidEdit) as exc:
                result = {"type": "note.error", "message": str(exc)}
            await hub.broadcast(note_id, result)
    except WebSocketDisconnect:
        hub.remove(note_id, websocket)
