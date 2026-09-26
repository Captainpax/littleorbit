"""Authenticated partner-only relationship name endpoints."""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from ..couple_access import active_member
from ..database import session_scope
from ..dependencies import current_account
from ..models import Account
from ..profile_schemas import PartnerNameMutation, PartnerNameReset, PartnerNameState
from ..relationship_name_service import mutate_partner_name

router = APIRouter(prefix="/v1/couple/current/partner-name", tags=["profile"])


@router.put("", response_model=PartnerNameState)
async def put_partner_name(
    payload: PartnerNameMutation,
    actor: Account = Depends(current_account),
    session: AsyncSession = Depends(session_scope),
) -> PartnerNameState:
    """Assign the caller's current partner a shared relationship name."""

    member = await active_member(session, actor.id)
    try:
        result = await mutate_partner_name(
            session,
            member,
            actor.id,
            payload.operation_id,
            payload.expected_revision,
            payload.display_name,
        )
    except ValueError as error:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(error)) from error
    await session.commit()
    return result


@router.post("/reset", response_model=PartnerNameState)
async def reset_partner_name(
    payload: PartnerNameReset,
    actor: Account = Depends(current_account),
    session: AsyncSession = Depends(session_scope),
) -> PartnerNameState:
    """Reset only the relationship name previously controlled by the caller."""

    member = await active_member(session, actor.id)
    result = await mutate_partner_name(
        session,
        member,
        actor.id,
        payload.operation_id,
        payload.expected_revision,
        None,
    )
    await session.commit()
    return result
