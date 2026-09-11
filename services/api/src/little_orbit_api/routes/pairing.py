"""Atomic, confirmed, two-person pairing routes."""

from datetime import timedelta
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..clock import SystemClock
from ..config import Settings, get_settings
from ..database import session_scope
from ..dependencies import current_account
from ..models import Account, Couple, CoupleMember, PairCode
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


@router.post("/codes", response_model=PairCodeResponse, status_code=status.HTTP_201_CREATED)
async def create_code(
    actor: Account = Depends(current_account),
    session: AsyncSession = Depends(session_scope),
    settings: Settings = Depends(get_settings),
) -> PairCodeResponse:
    """Create a ten-minute unambiguous pair code for a verified unpaired account."""

    if actor.verified_at is None or await _active_couple_id(session, actor.id):
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
    session: AsyncSession = Depends(session_scope),
    settings: Settings = Depends(get_settings),
) -> PairingState:
    """Lock and reserve a valid pair code for creator confirmation."""

    now = SystemClock().now()
    digest = hash_token(payload.code, settings.token_pepper.get_secret_value())
    code = await session.scalar(
        select(PairCode)
        .where(
            PairCode.code_hash == digest,
            PairCode.expires_at > now,
            PairCode.consumed_at.is_(None),
        )
        .with_for_update()
    )
    invalid = code is None or code.creator_id == actor.id or code.pending_partner_id is not None
    invalid = (
        invalid
        or actor.verified_at is None
        or await _active_couple_id(session, actor.id) is not None
    )
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
    code = await session.scalar(
        select(PairCode)
        .where(
            PairCode.id == payload.request_id,
            PairCode.creator_id == actor.id,
            PairCode.expires_at > now,
            PairCode.consumed_at.is_(None),
        )
        .with_for_update()
    )
    if code is None or code.pending_partner_id is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Pairing request is invalid or expired")
    account_ids = (actor.id, code.pending_partner_id)
    locked_accounts = list(
        await session.scalars(
            select(Account)
            .where(Account.id.in_(account_ids))
            .order_by(Account.id)
            .with_for_update()
        )
    )
    if len(locked_accounts) != 2:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Pairing request is invalid or expired")
    active_count = await session.scalar(
        select(func.count())
        .select_from(CoupleMember)
        .where(CoupleMember.account_id.in_(account_ids), CoupleMember.left_at.is_(None))
    )
    if active_count:
        raise HTTPException(status.HTTP_409_CONFLICT, "One account is already paired")
    couple = Couple(created_at=now, updated_at=now, proximity_threshold_m=100.0)
    session.add(couple)
    await session.flush()
    session.add_all(
        [
            CoupleMember(couple_id=couple.id, account_id=account_id, joined_at=now)
            for account_id in account_ids
        ]
    )
    code.consumed_at = now
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
