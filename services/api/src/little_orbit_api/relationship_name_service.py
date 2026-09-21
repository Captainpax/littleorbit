"""Partner-only relationship names with privacy-safe fallbacks and replay protection."""

import hashlib
import json
import re
import unicodedata
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime
from typing import cast
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from .activity_service import record_activity
from .clock import SystemClock
from .couple_access import lock_couple
from .models import Account, CoupleMember
from .profile_models import RelationshipName, RelationshipNameOperation
from .profile_schemas import PartnerNameState

_EMAIL = re.compile(r"\b[^\s@]+@[^\s@]+\.[^\s@]+\b", re.IGNORECASE)
_URL = re.compile(
    r"(?:https?://|www\.)|(?:\b[a-z0-9-]+\.)+(?:com|net|org|io|app|dev|co|me)\b",
    re.IGNORECASE,
)
_PHONE = re.compile(r"^[+()\d.\-\s]+$")


@dataclass(frozen=True)
class VisibleRelationshipName:
    """Effective name and relationship-scoped assignment metadata."""

    display_name: str
    revision: int
    partner_assigned: bool


def normalize_assigned_name(value: str) -> str:
    """Normalize a friendly Unicode name and reject contact or control data."""

    normalized = unicodedata.normalize("NFKC", value).strip()
    if not 1 <= len(normalized) <= 40:
        raise ValueError("Name must be between 1 and 40 characters")
    if any(_forbidden_character(character) for character in normalized):
        raise ValueError("Name cannot contain controls or line breaks")
    if _looks_like_contact(normalized):
        raise ValueError("Name cannot be an email address, phone number, or URL")
    return normalized


def safe_account_name(value: str, *, is_viewer: bool) -> str:
    """Use a non-contact account name or a relationship-safe generic label."""

    normalized = unicodedata.normalize("NFKC", value).strip()
    invalid = not normalized or len(normalized) > 80
    invalid = invalid or any(_forbidden_character(character) for character in normalized)
    if invalid or _looks_like_contact(normalized):
        return "You" if is_viewer else "Your partner"
    return normalized


async def visible_relationship_names(
    session: AsyncSession,
    couple_id: UUID,
    subject_ids: Iterable[UUID],
    viewer_id: UUID,
) -> dict[UUID, VisibleRelationshipName]:
    """Resolve authorized active-relationship names in one bounded query batch."""

    ids = tuple(dict.fromkeys(subject_ids))
    if not ids:
        return {}
    accounts = {
        item.id: item
        for item in await session.scalars(select(Account).where(Account.id.in_(ids)))
    }
    assignments = {
        item.subject_account_id: item
        for item in await session.scalars(
            select(RelationshipName).where(
                RelationshipName.couple_id == couple_id,
                RelationshipName.subject_account_id.in_(ids),
            )
        )
    }
    return {
        subject_id: _visible_name(accounts.get(subject_id), assignments.get(subject_id), viewer_id)
        for subject_id in ids
    }


async def mutate_partner_name(
    session: AsyncSession,
    member: CoupleMember,
    actor_id: UUID,
    operation_id: UUID,
    expected_revision: int,
    assigned_name: str | None,
) -> PartnerNameState:
    """Set or reset only the caller's partner name under the couple lock."""

    if member.account_id != actor_id:
        raise HTTPException(status.HTTP_409_CONFLICT, "Pairing state changed; retry")
    await lock_couple(session, member.couple_id)
    partner_id = await _active_partner_id(session, member.couple_id, actor_id)
    action = "reset" if assigned_name is None else "set"
    normalized = None if assigned_name is None else normalize_assigned_name(assigned_name)
    request_hash = _request_hash(action, expected_revision, normalized)
    replay = await _operation(session, actor_id, operation_id)
    if replay is not None:
        return _replay_result(replay, member.couple_id, partner_id, request_hash)
    record = await _name_record(session, member.couple_id, partner_id, lock=True)
    current_revision = 0 if record is None else record.revision
    if current_revision != expected_revision:
        raise HTTPException(status.HTTP_409_CONFLICT, "Name changed; refresh and retry")
    now = SystemClock().now()
    record = _apply_name_change(
        session, record, member.couple_id, partner_id, actor_id, normalized, now
    )
    partner = await session.get(Account, partner_id)
    if partner is None:
        raise HTTPException(status.HTTP_409_CONFLICT, "Pairing state changed; retry")
    result = _mutation_result(record, partner.display_name)
    session.add(
        RelationshipNameOperation(
            couple_id=member.couple_id,
            subject_account_id=partner_id,
            assigned_by_account_id=actor_id,
            operation_id=operation_id,
            action=action,
            request_hash=request_hash,
            result_json=result.model_dump(mode="json"),
            created_at=now,
        )
    )
    await record_activity(
        session,
        member.couple_id,
        actor_id,
        "relationship_name_changed",
        f"relationship-name:{operation_id}",
    )
    return result


def _apply_name_change(
    session: AsyncSession,
    record: RelationshipName | None,
    couple_id: UUID,
    subject_id: UUID,
    actor_id: UUID,
    assigned_name: str | None,
    now: datetime,
) -> RelationshipName:
    if record is None:
        record = RelationshipName(
            couple_id=couple_id,
            subject_account_id=subject_id,
            assigned_by_account_id=actor_id,
            assigned_name=assigned_name,
            revision=1,
            updated_at=now,
        )
        session.add(record)
        return record
    if record.assigned_by_account_id != actor_id:
        raise HTTPException(status.HTTP_409_CONFLICT, "Name ownership changed; refresh")
    record.assigned_name = assigned_name
    record.revision += 1
    record.updated_at = now
    return record


async def _active_partner_id(
    session: AsyncSession, couple_id: UUID, actor_id: UUID
) -> UUID:
    partner_id = await session.scalar(
        select(CoupleMember.account_id).where(
            CoupleMember.couple_id == couple_id,
            CoupleMember.account_id != actor_id,
            CoupleMember.left_at.is_(None),
        )
    )
    if partner_id is None:
        raise HTTPException(status.HTTP_409_CONFLICT, "Pairing state changed; retry")
    return cast(UUID, partner_id)


async def _name_record(
    session: AsyncSession, couple_id: UUID, subject_id: UUID, *, lock: bool = False
) -> RelationshipName | None:
    statement = select(RelationshipName).where(
        RelationshipName.couple_id == couple_id,
        RelationshipName.subject_account_id == subject_id,
    )
    if lock:
        statement = statement.with_for_update()
    return cast(RelationshipName | None, await session.scalar(statement))


async def _operation(
    session: AsyncSession, actor_id: UUID, operation_id: UUID
) -> RelationshipNameOperation | None:
    return cast(
        RelationshipNameOperation | None,
        await session.scalar(
            select(RelationshipNameOperation).where(
                RelationshipNameOperation.assigned_by_account_id == actor_id,
                RelationshipNameOperation.operation_id == operation_id,
            )
        ),
    )


def _replay_result(
    replay: RelationshipNameOperation,
    couple_id: UUID,
    subject_id: UUID,
    request_hash: str,
) -> PartnerNameState:
    valid_scope = replay.couple_id == couple_id and replay.subject_account_id == subject_id
    if not valid_scope or replay.request_hash != request_hash:
        raise HTTPException(status.HTTP_409_CONFLICT, "Operation ID was already used")
    return PartnerNameState.model_validate(replay.result_json)


def _mutation_result(record: RelationshipName, account_name: str) -> PartnerNameState:
    assigned = record.assigned_name
    return PartnerNameState(
        display_name=assigned or safe_account_name(account_name, is_viewer=False),
        assigned_name=assigned,
        revision=record.revision,
        partner_assigned=assigned is not None,
        updated_at=record.updated_at,
    )


def _visible_name(
    account: Account | None, assignment: RelationshipName | None, viewer_id: UUID
) -> VisibleRelationshipName:
    is_viewer = account is not None and account.id == viewer_id
    fallback = safe_account_name(account.display_name, is_viewer=is_viewer) if account else (
        "You" if is_viewer else "Your partner"
    )
    return VisibleRelationshipName(
        display_name=assignment.assigned_name if assignment and assignment.assigned_name else fallback,
        revision=assignment.revision if assignment else 0,
        partner_assigned=bool(assignment and assignment.assigned_name),
    )


def _request_hash(action: str, expected_revision: int, assigned_name: str | None) -> str:
    payload = json.dumps(
        {"action": action, "expected_revision": expected_revision, "name": assigned_name},
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _forbidden_character(character: str) -> bool:
    category = unicodedata.category(character)
    return category in {"Cc", "Cs", "Zl", "Zp"} or (category == "Cf" and character != "\u200d")


def _looks_like_contact(value: str) -> bool:
    digits = sum(character.isdigit() for character in value)
    return bool(
        _EMAIL.search(value)
        or _URL.search(value)
        or (digits >= 7 and _PHONE.fullmatch(value))
    )
