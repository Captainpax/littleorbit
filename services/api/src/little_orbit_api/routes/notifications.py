"""Authenticated preferences, per-device delivery, and foreground availability hints."""

import asyncio
from contextlib import suppress
from typing import cast
from uuid import UUID, uuid4

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Query,
    Response,
    WebSocket,
    WebSocketDisconnect,
    status,
)
from sqlalchemy import select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from ..clock import SystemClock
from ..couple_access import active_member, lock_couple
from ..database import SessionFactory, session_scope
from ..dependencies import current_account
from ..interaction_models import Smooch
from ..models import Account, CoupleMember
from ..notification_hub import NotificationConnectionHub
from ..notification_models import NotificationDelivery, NotificationDevice, NotificationEvent
from ..notification_schemas import (
    NotificationDeliveryAck,
    NotificationDeviceResponse,
    NotificationDeviceUpsert,
    NotificationEventResponse,
    NotificationPreferencesResponse,
    NotificationPreferencesUpdate,
)
from ..notification_service import (
    discard_disabled_events,
    ensure_pending_deliveries,
    ensure_quiz_available_event,
    event_response,
    preferences_for,
    preferences_response,
)
from ..quiz_v2_service import materialize_day, utc_today
from ..socket_auth import SocketIdentity, authenticate_socket, socket_session_active
from .notes import _compatible_socket

router = APIRouter(prefix="/v1", tags=["notifications"])


@router.get("/notification-preferences", response_model=NotificationPreferencesResponse)
async def get_preferences(
    actor: Account = Depends(current_account),
    session: AsyncSession = Depends(session_scope),
) -> NotificationPreferencesResponse:
    """Return account-wide defaults or saved notification choices."""

    item = await preferences_for(session, actor.id)
    await session.commit()
    return preferences_response(item)


@router.patch("/notification-preferences", response_model=NotificationPreferencesResponse)
async def update_preferences(
    payload: NotificationPreferencesUpdate,
    actor: Account = Depends(current_account),
    session: AsyncSession = Depends(session_scope),
) -> NotificationPreferencesResponse:
    """Replace all account-wide notification choices in one transaction."""

    item = await preferences_for(session, actor.id)
    for field, value in payload.model_dump().items():
        setattr(item, field, value)
    item.updated_at = SystemClock().now()
    await discard_disabled_events(session, item)
    await session.commit()
    return preferences_response(item)


@router.put("/notification-devices/{device_id}", response_model=NotificationDeviceResponse)
async def register_device(
    device_id: UUID,
    payload: NotificationDeviceUpsert,
    actor: Account = Depends(current_account),
    session: AsyncSession = Depends(session_scope),
) -> NotificationDeviceResponse:
    """Register or heartbeat the caller's random installation identifier."""

    now = SystemClock().now()
    statement = (
        insert(NotificationDevice)
        .values(
            id=uuid4(),
            account_id=actor.id,
            device_id=device_id,
            platform=payload.platform,
            app_version_code=payload.app_version_code,
            notifications_enabled=payload.notifications_enabled,
            last_seen_at=now,
            disabled_at=None,
        )
        .on_conflict_do_update(
            index_elements=["account_id", "device_id"],
            set_={
                "platform": payload.platform,
                "app_version_code": payload.app_version_code,
                "notifications_enabled": payload.notifications_enabled,
                "last_seen_at": now,
                "disabled_at": None,
            },
        )
        .returning(NotificationDevice.id)
    )
    record_id = await session.scalar(statement)
    device = await session.get(NotificationDevice, record_id)
    if device is None:
        raise HTTPException(status.HTTP_409_CONFLICT, "Device registration failed")
    if payload.notifications_enabled:
        await ensure_pending_deliveries(session, device)
    await session.commit()
    return NotificationDeviceResponse(
        device_id=device.device_id,
        last_seen_at=device.last_seen_at,
        notifications_enabled=device.notifications_enabled,
        push_enabled=False,
    )


@router.delete("/notification-devices/{device_id}", status_code=status.HTTP_204_NO_CONTENT)
async def disable_device(
    device_id: UUID,
    actor: Account = Depends(current_account),
    session: AsyncSession = Depends(session_scope),
) -> Response:
    """Disable only the caller's matching installation without revealing others."""

    device = await session.scalar(
        select(NotificationDevice).where(
            NotificationDevice.account_id == actor.id,
            NotificationDevice.device_id == device_id,
        )
    )
    if device is not None:
        now = SystemClock().now()
        device.disabled_at = now
        device.notifications_enabled = False
        await session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/notifications/pending", response_model=list[NotificationEventResponse])
async def pending_events(
    device_id: UUID = Query(),
    actor: Account = Depends(current_account),
    session: AsyncSession = Depends(session_scope),
) -> list[NotificationEventResponse]:
    """Return only live, unacknowledged events for this account and installation."""

    member = await active_member(session, actor.id)
    await lock_couple(session, member.couple_id)
    device = await _owned_device(session, actor.id, device_id)
    await _ensure_quiz_alert(session, member, actor.id)
    await ensure_pending_deliveries(session, device)
    rows = list(
        await session.scalars(
            select(NotificationEvent)
            .join(NotificationDelivery, NotificationDelivery.event_id == NotificationEvent.id)
            .where(
                NotificationDelivery.device_id == device.id,
                NotificationDelivery.displayed_at.is_(None),
                NotificationEvent.recipient_id == actor.id,
                NotificationEvent.couple_id == member.couple_id,
                NotificationEvent.expires_at > SystemClock().now(),
            )
            .order_by(NotificationEvent.created_at)
            .limit(50)
        )
    )
    resolved: list[NotificationEventResponse] = []
    for event in rows:
        item = await event_response(session, event)
        if item is None:
            await session.delete(event)
        else:
            resolved.append(item)
    await session.commit()
    return resolved


async def _ensure_quiz_alert(
    session: AsyncSession, member: CoupleMember, account_id: UUID
) -> None:
    """Add today's quiz alert without blocking unrelated notification delivery."""

    try:
        async with session.begin_nested():
            day = await materialize_day(session, member, utc_today())
            await ensure_quiz_available_event(session, day, account_id)
    except HTTPException as error:
        if error.status_code != status.HTTP_503_SERVICE_UNAVAILABLE:
            raise


@router.post("/notifications/deliveries/ack", status_code=status.HTTP_204_NO_CONTENT)
async def acknowledge_events(
    payload: NotificationDeliveryAck,
    actor: Account = Depends(current_account),
    session: AsyncSession = Depends(session_scope),
) -> Response:
    """Acknowledge only displayed events owned by this account and installation."""

    member = await active_member(session, actor.id)
    await lock_couple(session, member.couple_id)
    device = await _owned_device(session, actor.id, payload.device_id)
    deliveries = list(
        await session.scalars(
            select(NotificationDelivery)
            .join(NotificationEvent, NotificationEvent.id == NotificationDelivery.event_id)
            .where(
                NotificationDelivery.device_id == device.id,
                NotificationDelivery.event_id.in_(payload.event_ids),
                NotificationEvent.recipient_id == actor.id,
                NotificationEvent.couple_id == member.couple_id,
            )
            .with_for_update()
        )
    )
    now = SystemClock().now()
    for delivery in deliveries:
        if delivery.displayed_at is None:
            delivery.displayed_at = now
    acknowledged_event_ids = [delivery.event_id for delivery in deliveries]
    smooch_ids = list(
        await session.scalars(
            select(NotificationEvent.source_id).where(
                NotificationEvent.id.in_(acknowledged_event_ids),
                NotificationEvent.kind == "smooch_received",
            )
        )
    )
    if smooch_ids:
        await session.execute(
            update(Smooch)
            .where(
                Smooch.id.in_(smooch_ids),
                Smooch.recipient_id == actor.id,
                Smooch.delivered_at.is_(None),
            )
            .values(delivered_at=now)
        )
    await session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


async def _owned_device(
    session: AsyncSession, account_id: UUID, device_id: UUID
) -> NotificationDevice:
    device = await session.scalar(
        select(NotificationDevice).where(
            NotificationDevice.account_id == account_id,
            NotificationDevice.device_id == device_id,
            NotificationDevice.disabled_at.is_(None),
        )
    )
    if device is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Notification device is unavailable")
    return device


@router.websocket("/notifications")
async def notification_socket(websocket: WebSocket, device_id: UUID = Query()) -> None:
    """Hold a foreground-only content-free availability channel."""

    if not await _compatible_socket(websocket):
        return
    identity = await authenticate_socket(websocket.headers.get("authorization", ""))
    if identity is None or not await _socket_device(identity, device_id):
        await websocket.close(code=4401)
        return
    await websocket.accept()
    hub = cast(NotificationConnectionHub, websocket.app.state.notification_connections)
    hub.add(identity.account_id, websocket)
    if not await _socket_device(identity, device_id):
        hub.remove(identity.account_id, websocket)
        await websocket.close(code=4401)
        return
    await websocket.send_json({"type": "notification.ready"})
    try:
        while True:
            with suppress(TimeoutError):
                await asyncio.wait_for(websocket.receive_text(), timeout=30)
            if not await _socket_device(identity, device_id):
                await websocket.close(code=4401)
                return
    except WebSocketDisconnect:
        pass
    finally:
        hub.remove(identity.account_id, websocket)


async def _socket_device(identity: SocketIdentity, device_id: UUID) -> bool:
    if not await socket_session_active(identity):
        return False
    async with SessionFactory() as session:
        return (
            await session.scalar(
                select(NotificationDevice.id).where(
                    NotificationDevice.account_id == identity.account_id,
                    NotificationDevice.device_id == device_id,
                    NotificationDevice.disabled_at.is_(None),
                )
            )
            is not None
        )
