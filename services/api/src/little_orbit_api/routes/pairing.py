"""Atomic, confirmed, two-person pairing routes."""

from datetime import timedelta
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..clock import SystemClock
from ..config import Settings, get_settings
from ..database import session_scope
from ..dependencies import current_account, request_client_ip
from ..models import Account, Couple, CoupleMember, PairCode, SecurityEvent
from ..rate_limit import consume_rate_limits, request_rules
from ..relationship_service import lock_accounts
from ..schemas import (
    PairCodeResponse,
    PairConfirmRequest,
    PairingState,
    PairPendingResponse,
    PairRedeemRequest,
)
from ..security import hash_token, new_pair_code

router = APIRouter(prefix="/v1/pairing", tags=["pairing"])


async def _active_couple_id(session: AsyncSession, account_id: UUID) -> UUID | None:
    couple_id = await session.scalar(
        select(CoupleMember.couple_id).where(
            CoupleMember.account_id == account_id,
            CoupleMember.left_at.is_(None),
        )
    )
    return couple_id


def _eligible(account: Account) -> bool:
    return (
        account.verified_at is not None
        and account.suspended_at is None
        and account.deleted_at is None
    )


async def _locked_active_memberships(
    session: AsyncSession, account_ids: tuple[UUID, UUID]
) -> list[CoupleMember]:
    return list(
        await session.scalars(
            select(CoupleMember)
            .where(
                CoupleMember.account_id.in_(account_ids),
                CoupleMember.left_at.is_(None),
            )
            .order_by(CoupleMember.account_id)
            .with_for_update()
        )
    )


async def _redeem_allowed(
    client_ip: str, actor_id: UUID, settings: Settings
) -> bool:
    decision = await consume_rate_limits(
        request_rules(
            "pair-redeem",
            client_ip,
            str(actor_id),
            ip_limit=settings.pair_redeem_ip_per_hour,
            subject_limit=settings.pair_redeem_subject_per_hour,
            window=timedelta(hours=1),
        ),
        settings=settings,
    )
    return decision.allowed


async def _reject_redeem_limit(session: AsyncSession, actor_id: UUID) -> None:
    session.add(
        SecurityEvent(
            actor_id=actor_id,
            event_type="pair_redeem_rate_limit",
            outcome="blocked",
            metadata_json={},
            created_at=SystemClock().now(),
        )
    )
    await session.commit()
    raise HTTPException(
        status.HTTP_429_TOO_MANY_REQUESTS,
        "Pairing is temporarily unavailable",
        headers={"Retry-After": "3600"},
    )


@router.post("/codes", response_model=PairCodeResponse, status_code=status.HTTP_201_CREATED)
async def create_code(
    actor: Account = Depends(current_account),
    session: AsyncSession = Depends(session_scope),
    settings: Settings = Depends(get_settings),
) -> PairCodeResponse:
    """Create a ten-minute unambiguous pair code for a verified unpaired account."""

    accounts = await lock_accounts(session, (actor.id,))
    if len(accounts) != 1 or not _eligible(accounts[0]):
        raise HTTPException(status.HTTP_409_CONFLICT, "Account cannot start pairing")
    if await _active_couple_id(session, actor.id):
        raise HTTPException(status.HTTP_409_CONFLICT, "Account cannot start pairing")
    now = SystemClock().now()
    raw = new_pair_code()
    expires = now + timedelta(minutes=10)
    session.add(
        PairCode(
            creator_id=actor.id,
            code_hash=hash_token(raw, settings.token_pepper.get_secret_value()),
            expires_at=expires,
            created_at=now,
        )
    )
    await session.commit()
    return PairCodeResponse(code=raw, expires_at=expires)


@router.post("/redeem", response_model=PairingState)
async def redeem_code(
    payload: PairRedeemRequest,
    actor: Account = Depends(current_account),
    client_ip: str = Depends(request_client_ip),
    session: AsyncSession = Depends(session_scope),
    settings: Settings = Depends(get_settings),
) -> PairingState:
    """Lock and reserve a valid pair code for creator confirmation."""

    if not await _redeem_allowed(client_ip, actor.id, settings):
        await _reject_redeem_limit(session, actor.id)
    now = SystemClock().now()
    digest = hash_token(payload.code, settings.token_pepper.get_secret_value())
    preview = await session.scalar(
        select(PairCode)
        .where(
            PairCode.code_hash == digest,
            PairCode.expires_at > now,
            PairCode.consumed_at.is_(None),
        )
    )
    if preview is None or preview.creator_id == actor.id:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Pair code is invalid or expired")
    account_ids = (actor.id, preview.creator_id)
    accounts = await lock_accounts(session, account_ids)
    locked_now = SystemClock().now()
    code = await session.scalar(
        select(PairCode)
        .where(
            PairCode.id == preview.id,
            PairCode.code_hash == digest,
            PairCode.expires_at > locked_now,
            PairCode.consumed_at.is_(None),
        )
        .with_for_update()
    )
    invalid = len(accounts) != 2 or any(not _eligible(item) for item in accounts)
    invalid = invalid or code is None or code.pending_partner_id is not None
    invalid = invalid or bool(await _locked_active_memberships(session, account_ids))
    if invalid or code is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Pair code is invalid or expired")
    code.pending_partner_id = actor.id
    await session.commit()
    return PairingState(state="awaiting_creator_confirmation", request_id=code.id, couple_id=None)


@router.post("/confirm", response_model=PairingState)
async def confirm_pairing(
    payload: PairConfirmRequest,
    actor: Account = Depends(current_account),
    session: AsyncSession = Depends(session_scope),
) -> PairingState:
    """Create a two-member couple and consume the code in one transaction."""

    now = SystemClock().now()
    preview = await session.scalar(
        select(PairCode)
        .where(
            PairCode.id == payload.request_id,
            PairCode.creator_id == actor.id,
            PairCode.expires_at > now,
            PairCode.consumed_at.is_(None),
        )
    )
    if preview is None or preview.pending_partner_id is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Pairing request is invalid or expired")
    account_ids = (actor.id, preview.pending_partner_id)
    locked_accounts = await lock_accounts(session, account_ids)
    locked_now = SystemClock().now()
    code = await session.scalar(
        select(PairCode)
        .where(
            PairCode.id == payload.request_id,
            PairCode.creator_id == actor.id,
            PairCode.pending_partner_id == preview.pending_partner_id,
            PairCode.expires_at > locked_now,
            PairCode.consumed_at.is_(None),
        )
        .with_for_update()
    )
    eligible = len(locked_accounts) == 2 and all(
        _eligible(account) for account in locked_accounts
    )
    if code is None or not eligible:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Pairing request is invalid or expired")
    if await _locked_active_memberships(session, account_ids):
        raise HTTPException(status.HTTP_409_CONFLICT, "One account is already paired")
    couple = Couple(created_at=locked_now, updated_at=locked_now, proximity_threshold_m=100.0)
    session.add(couple)
    await session.flush()
    session.add_all(
        [
            CoupleMember(couple_id=couple.id, account_id=account_id, joined_at=locked_now)
            for account_id in account_ids
        ]
    )
    code.consumed_at = locked_now
    await session.commit()
    return PairingState(state="paired", request_id=code.id, couple_id=couple.id)


@router.get("/pending", response_model=PairPendingResponse)
async def pending_pairing(
    actor: Account = Depends(current_account),
    session: AsyncSession = Depends(session_scope),
) -> PairPendingResponse:
    """Show the creator a reserved partner's display name for explicit confirmation."""

    row = (
        await session.execute(
            select(PairCode, Account.display_name)
            .join(Account, Account.id == PairCode.pending_partner_id)
            .where(
                PairCode.creator_id == actor.id,
                PairCode.pending_partner_id.is_not(None),
                PairCode.consumed_at.is_(None),
                PairCode.expires_at > SystemClock().now(),
            )
            .order_by(PairCode.created_at.desc())
            .limit(1)
        )
    ).first()
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No pairing awaits confirmation")
    code, partner_name = row
    return PairPendingResponse(
        request_id=code.id,
        partner_display_name=partner_name,
        expires_at=code.expires_at,
    )
