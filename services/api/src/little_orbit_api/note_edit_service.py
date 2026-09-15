"""Transactional operational-transform rules for live shared notes."""

from uuid import UUID

from fastapi import HTTPException
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from .activity_service import record_activity
from .clock import SystemClock
from .couple_access import lock_couple
from .database import SessionFactory
from .domain.notes import Delete, Edit, Insert, InvalidEdit, apply_edit, transform
from .models import Account, CoupleMember, Note, NoteOperation, Session
from .notification_service import enqueue_note_edit_event


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


async def apply_note_edit(
    note_id: UUID,
    account_id: UUID,
    message: NoteEditMessage,
    *,
    session_token_hash: str,
    partner_viewing: bool = False,
) -> dict[str, object]:
    """Authorize, serialize, apply, and acknowledge one retry-safe edit."""

    async with SessionFactory() as db:
        couple_id = await _authorized_couple(
            db, note_id, account_id, session_token_hash
        )
        result = await _apply_locked(
            db, note_id, account_id, couple_id, message, partner_viewing
        )
        await db.commit()
        return result


async def _authorized_couple(
    db: AsyncSession,
    note_id: UUID,
    account_id: UUID,
    session_token_hash: str,
) -> UUID:
    now = SystemClock().now()
    account = await db.get(Account, account_id, with_for_update=True)
    if account is None or account.suspended_at is not None or account.deleted_at is not None:
        raise NoteAccessRevoked
    live_session = await db.scalar(
        select(Session)
        .where(
            Session.account_id == account_id,
            Session.token_hash == session_token_hash,
            Session.revoked_at.is_(None),
            Session.expires_at > now,
        )
        .with_for_update()
    )
    if live_session is None:
        raise NoteAccessRevoked
    couple_id = await db.scalar(
        select(CoupleMember.couple_id)
        .join(Note, Note.couple_id == CoupleMember.couple_id)
        .where(
            CoupleMember.account_id == account_id,
            CoupleMember.left_at.is_(None),
            Note.id == note_id,
            Note.archived_at.is_(None),
        )
    )
    if couple_id is None:
        raise NoteAccessRevoked
    try:
        await lock_couple(db, couple_id)
    except HTTPException as revoked:
        raise NoteAccessRevoked from revoked
    return couple_id


async def _apply_locked(
    db: AsyncSession,
    note_id: UUID,
    account_id: UUID,
    couple_id: UUID,
    message: NoteEditMessage,
    partner_viewing: bool,
) -> dict[str, object]:
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
    prior_body = note.body
    note.body = _apply_non_empty_edit(note.body, edit)
    note.revision += 1
    note.updated_at = SystemClock().now()
    db.add(_operation(note, account_id, message, edit))
    await record_activity(
        db, couple_id, account_id, "note_updated", f"note:edit:{message.operation_id}",
        target_type="note", target_id=note.id, target_title=note.title,
    )
    notified = None
    if note.body != prior_body:
        notified = await enqueue_note_edit_event(
            db, couple_id, account_id, note_id, partner_viewing=partner_viewing
        )
    result = _ack(note, message)
    if notified is not None:
        result["_notify_account_id"] = str(notified)
    return result


def _operation(
    note: Note, account_id: UUID, message: NoteEditMessage, edit: Edit
) -> NoteOperation:
    return NoteOperation(
        note_id=note.id,
        operation_id=message.operation_id,
        actor_id=account_id,
        base_revision=message.base_revision,
        resulting_revision=note.revision,
        edit=_stored_edit(edit),
        applied_at=SystemClock().now(),
    )


def _ack(note: Note, message: NoteEditMessage) -> dict[str, object]:
    return {
        "type": "note.ack",
        "operation_id": str(message.operation_id),
        "revision": note.revision,
        "body": note.body,
        "transformed": message.base_revision != note.revision - 1,
        "duplicate": False,
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


def _duplicate_ack(
    existing: NoteOperation, note: Note | None, message: NoteEditMessage
) -> dict[str, object]:
    return {
        "type": "note.ack",
        "operation_id": str(message.operation_id),
        "revision": note.revision if note else existing.resulting_revision,
        "body": note.body if note else "",
        "transformed": existing.base_revision != existing.resulting_revision - 1,
        "duplicate": True,
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
