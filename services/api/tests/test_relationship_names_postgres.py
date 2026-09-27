"""Optional PostgreSQL coverage for shared-name races, privacy, and lifecycle."""

import asyncio
import os
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import httpx
import pytest
import pytest_asyncio
from sqlalchemy import func, inspect, select, text

pytestmark = [
    pytest.mark.skipif(
        not os.getenv("LITTLE_ORBIT_TEST_DATABASE_URL"),
        reason="set LITTLE_ORBIT_TEST_DATABASE_URL to an isolated PostgreSQL database",
    ),
    pytest.mark.asyncio(loop_scope="session"),
]

from little_orbit_api.activity_models import ActivityEvent  # noqa: E402
from little_orbit_api.config import get_settings  # noqa: E402
from little_orbit_api.database import Base, SessionFactory, engine  # noqa: E402
from little_orbit_api.interaction_models import Smooch  # noqa: E402
from little_orbit_api.main import create_app  # noqa: E402
from little_orbit_api.models import Account, Couple, CoupleMember, Session  # noqa: E402
from little_orbit_api.notification_models import NotificationEvent  # noqa: E402
from little_orbit_api.notification_service import event_response  # noqa: E402
from little_orbit_api.profile_models import (  # noqa: E402
    RelationshipName,
    RelationshipNameOperation,
)
from little_orbit_api.security import hash_password, hash_token  # noqa: E402


@pytest_asyncio.fixture(autouse=True, loop_scope="session")
async def clean_database() -> None:
    """Isolate destructive checks inside the explicitly named test database."""

    async with engine.begin() as connection:
        existing = set(await connection.run_sync(lambda sync: inspect(sync).get_table_names()))
        quote = connection.dialect.identifier_preparer.quote
        tables = ", ".join(
            quote(table.name) for table in Base.metadata.sorted_tables if table.name in existing
        )
        await connection.execute(text(f"TRUNCATE TABLE {tables} RESTART IDENTITY CASCADE"))


def _account(email: str) -> Account:
    now = datetime.now(UTC)
    return Account(
        email_normalized=email,
        password_hash=hash_password("valid-password-123"),
        display_name=email,
        is_adult=True,
        accepted_terms_version="2026-09-10",
        verified_at=now,
        is_admin=False,
        created_at=now,
        updated_at=now,
    )


def _session(account_id: UUID, raw_token: str) -> Session:
    now = datetime.now(UTC)
    return Session(
        account_id=account_id,
        token_hash=hash_token(raw_token, get_settings().token_pepper.get_secret_value()),
        expires_at=now + timedelta(hours=1),
        authenticated_at=now,
        created_at=now,
    )


async def _paired_accounts() -> tuple[UUID, UUID, UUID, str, str]:
    now = datetime.now(UTC)
    actor = _account("actor@example.com")
    partner = _account("partner@example.com")
    couple = Couple(created_at=now, updated_at=now)
    actor_token = "a" * 40
    partner_token = "b" * 40
    async with SessionFactory() as session:
        session.add_all([actor, partner, couple])
        await session.flush()
        session.add_all(
            [
                CoupleMember(couple_id=couple.id, account_id=actor.id, joined_at=now),
                CoupleMember(couple_id=couple.id, account_id=partner.id, joined_at=now),
                _session(actor.id, actor_token),
                _session(partner.id, partner_token),
            ]
        )
        await session.commit()
    return actor.id, partner.id, couple.id, actor_token, partner_token


async def test_name_lifecycle_is_shared_idempotent_and_purged() -> None:
    actor_id, partner_id, couple_id, actor_token, partner_token = await _paired_accounts()
    app = create_app()
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://localhost"
    ) as client:
        actor_headers = {"Authorization": f"Bearer {actor_token}"}
        partner_headers = {"Authorization": f"Bearer {partner_token}"}
        await _assert_shared_name_views(client, actor_headers, partner_headers)
        await _assert_notification_name(couple_id, actor_id, partner_id)
        await _assert_reset_export_and_unpair(client, actor_headers)

    async with SessionFactory() as session:
        assert await session.scalar(select(func.count()).select_from(RelationshipName)) == 0
        assert (
            await session.scalar(select(func.count()).select_from(RelationshipNameOperation))
            == 0
        )
        assert await session.scalar(select(func.count()).select_from(ActivityEvent)) == 0


async def _assert_shared_name_views(
    client: httpx.AsyncClient,
    actor_headers: dict[str, str],
    partner_headers: dict[str, str],
) -> None:
    payload = {
        "operation_id": str(uuid4()),
        "expected_revision": 0,
        "display_name": "Moon Owl 🦉",
    }
    created = await client.put(
        "/v1/couple/current/partner-name", headers=actor_headers, json=payload
    )
    replay = await client.put(
        "/v1/couple/current/partner-name", headers=actor_headers, json=payload
    )
    other_name = await client.put(
        "/v1/couple/current/partner-name",
        headers=partner_headers,
        json={
            "operation_id": str(uuid4()),
            "expected_revision": 0,
            "display_name": "Starlight",
        },
    )
    actor_profile = await client.get("/v1/account/orbit-profile", headers=actor_headers)
    partner_profile = await client.get("/v1/account/orbit-profile", headers=partner_headers)
    conflict = await client.put(
        "/v1/couple/current/partner-name",
        headers=actor_headers,
        json={**payload, "display_name": "Different"},
    )
    stale = await client.put(
        "/v1/couple/current/partner-name",
        headers=actor_headers,
        json={
            "operation_id": str(uuid4()),
            "expected_revision": 0,
            "display_name": "Different",
        },
    )
    assert created.status_code == replay.status_code == other_name.status_code == 200
    assert created.json() == replay.json()
    assert conflict.status_code == stale.status_code == 409
    assert actor_profile.json()["me"]["display_name"] == "Starlight"
    assert actor_profile.json()["partner"]["display_name"] == "Moon Owl 🦉"
    assert partner_profile.json()["me"]["display_name"] == "Moon Owl 🦉"
    assert partner_profile.json()["partner"]["display_name"] == "Starlight"


async def _assert_reset_export_and_unpair(
    client: httpx.AsyncClient, actor_headers: dict[str, str]
) -> None:
    reset = await client.post(
        "/v1/couple/current/partner-name/reset",
        headers=actor_headers,
        json={"operation_id": str(uuid4()), "expected_revision": 1},
    )
    exported = await client.get("/v1/account/export", headers=actor_headers)
    assert reset.status_code == exported.status_code == 200
    assert reset.json()["display_name"] == "Your partner"
    assert len(exported.json()["data"]["relationships"][0]["relationship_names"]) == 2
    unpaired = await client.post("/v1/couple/unpair", headers=actor_headers)
    assert unpaired.status_code == 200


async def _assert_notification_name(
    couple_id: UUID, actor_id: UUID, partner_id: UUID
) -> None:
    now = datetime.now(UTC)
    async with SessionFactory() as session:
        smooch = Smooch(
            operation_id=uuid4(),
            couple_id=couple_id,
            sender_id=actor_id,
            recipient_id=partner_id,
            emoji="😘",
            phrase_key="kiss",
            sent_at=now,
        )
        session.add(smooch)
        await session.flush()
        event = NotificationEvent(
            recipient_id=partner_id,
            couple_id=couple_id,
            actor_id=actor_id,
            kind="smooch_received",
            source_id=smooch.id,
            dedupe_key=f"test:{smooch.id}",
            created_at=now,
            expires_at=now + timedelta(hours=1),
        )
        session.add(event)
        await session.flush()
        response = await event_response(session, event)
        assert response is not None and response.actor_display_name == "Starlight"
        await session.rollback()


async def test_concurrent_devices_cannot_overwrite_the_same_revision() -> None:
    _, _, _, actor_token, _ = await _paired_accounts()
    headers = {"Authorization": f"Bearer {actor_token}"}
    app = create_app()

    async def send(name: str) -> int:
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://localhost"
        ) as client:
            response = await client.put(
                "/v1/couple/current/partner-name",
                headers=headers,
                json={
                    "operation_id": str(uuid4()),
                    "expected_revision": 0,
                    "display_name": name,
                },
            )
            return response.status_code

    statuses = await asyncio.gather(send("First"), send("Second"))
    assert sorted(statuses) == [200, 409]
    async with SessionFactory() as session:
        names = list(await session.scalars(select(RelationshipName)))
        activities = list(await session.scalars(select(ActivityEvent)))
        assert len(names) == len(activities) == 1
        assert activities[0].target_title is None


async def test_unpaired_account_cannot_probe_or_assign_a_name() -> None:
    account = _account("alone@example.com")
    token = "z" * 40
    async with SessionFactory() as session:
        session.add(account)
        await session.flush()
        session.add(_session(account.id, token))
        await session.commit()
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=create_app()), base_url="http://localhost"
    ) as client:
        response = await client.put(
            "/v1/couple/current/partner-name",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "operation_id": str(uuid4()),
                "expected_revision": 0,
                "display_name": "Nobody",
            },
        )
    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "relationship_inactive"
    async with SessionFactory() as session:
        assert await session.scalar(select(func.count()).select_from(RelationshipName)) == 0
