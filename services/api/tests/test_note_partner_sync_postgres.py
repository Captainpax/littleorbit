"""PostgreSQL proof that one shared document converges for both partners."""

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

from little_orbit_api.config import get_settings  # noqa: E402
from little_orbit_api.database import Base, SessionFactory, engine  # noqa: E402
from little_orbit_api.main import create_app  # noqa: E402
from little_orbit_api.models import Account, Couple, CoupleMember, Note, Session  # noqa: E402
from little_orbit_api.note_edit_service import (  # noqa: E402
    NoteEditMessage,
    apply_note_edit,
)
from little_orbit_api.notification_models import (  # noqa: E402
    NotificationDelivery,
    NotificationDevice,
    NotificationEvent,
)
from little_orbit_api.security import hash_token  # noqa: E402


@pytest_asyncio.fixture(autouse=True, loop_scope="session")
async def clean_database() -> None:
    """Keep the paired convergence check inside the explicitly named test database."""

    async with engine.begin() as connection:
        existing = set(await connection.run_sync(lambda sync: inspect(sync).get_table_names()))
        quote = connection.dialect.identifier_preparer.quote
        tables = ", ".join(
            quote(table.name) for table in Base.metadata.sorted_tables if table.name in existing
        )
        await connection.execute(text(f"TRUNCATE TABLE {tables} RESTART IDENTITY CASCADE"))


async def test_created_note_and_live_edits_converge_for_both_partners() -> None:
    """A newly created note is listed and editable from either active account."""

    first, second, first_token, second_token = await _seed_pair()
    app = create_app()
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://localhost"
    ) as client:
        created = await client.post(
            "/v1/notes",
            headers=_headers(first_token),
            json={"operation_id": str(uuid4()), "title": "Shared", "body": "hello"},
        )
        assert created.status_code == 201
        note_id = UUID(created.json()["id"])
        recovered = await client.post(
            "/v1/notes",
            headers=_headers(first_token),
            json={"operation_id": str(uuid4()), "title": "Shared", "body": "hello"},
        )
        assert recovered.status_code == 201
        assert recovered.json()["id"] == str(note_id)
        async with SessionFactory() as session:
            assert await session.scalar(select(func.count()).select_from(Note)) == 1
        second_list = await client.get("/v1/notes", headers=_headers(second_token))
        assert [(item["id"], item["body"]) for item in second_list.json()] == [
            (str(note_id), "hello")
        ]

        await _insert(note_id, first.id, first_token, 0, 5, " from A")
        after_first = await client.get("/v1/notes", headers=_headers(second_token))
        assert after_first.json()[0]["body"] == "hello from A"
        assert after_first.json()[0]["revision"] == 1

        await _insert(note_id, second.id, second_token, 1, 12, " + B")
        after_second = await client.get("/v1/notes", headers=_headers(first_token))
        assert after_second.json()[0]["body"] == "hello from A + B"
        assert after_second.json()[0]["revision"] == 2

    async with SessionFactory() as session:
        events = await session.scalar(
            select(func.count()).select_from(NotificationEvent).where(
                NotificationEvent.kind == "note_editing"
            )
        )
        deliveries = await session.scalar(
            select(func.count()).select_from(NotificationDelivery)
        )
    assert events == 2
    assert deliveries == 1


async def _seed_pair() -> tuple[Account, Account, str, str]:
    now = datetime.now(UTC)
    first = _account("note-first@example.com", now)
    second = _account("note-second@example.com", now)
    couple = Couple(
        id=uuid4(),
        proximity_threshold_m=100,
        proximity_algorithm_version=2,
        home_timezone="America/Los_Angeles",
        created_at=now,
        updated_at=now,
    )
    first_token = "first-note-session-with-enough-entropy"
    second_token = "second-note-session-with-enough-entropy"
    async with SessionFactory() as session:
        session.add_all([first, second, couple])
        session.add_all(
            CoupleMember(
                couple_id=couple.id,
                account_id=account.id,
                joined_at=now,
                intimacy_enabled=False,
                location_enabled=False,
            )
            for account in (first, second)
        )
        session.add_all(
            [_session(first.id, first_token, now), _session(second.id, second_token, now)]
        )
        session.add(
            NotificationDevice(
                account_id=second.id,
                device_id=uuid4(),
                platform="android",
                app_version_code=19,
                notifications_enabled=True,
                last_seen_at=now,
            )
        )
        await session.commit()
    return first, second, first_token, second_token


def _account(email: str, now: datetime) -> Account:
    return Account(
        id=uuid4(),
        email_normalized=email,
        password_hash="unused",
        display_name=email.split("@", 1)[0],
        is_adult=True,
        accepted_terms_version="2026-09-10",
        verified_at=now,
        is_admin=False,
        created_at=now,
        updated_at=now,
    )


def _session(account_id: UUID, raw_token: str, now: datetime) -> Session:
    return Session(
        account_id=account_id,
        token_hash=_token_hash(raw_token),
        expires_at=now + timedelta(hours=1),
        authenticated_at=now,
        admin_mfa_verified=False,
        created_at=now,
    )


async def _insert(
    note_id: UUID,
    account_id: UUID,
    raw_token: str,
    revision: int,
    position: int,
    value: str,
) -> None:
    result = await apply_note_edit(
        note_id,
        account_id,
        NoteEditMessage(
            operation_id=uuid4(),
            base_revision=revision,
            kind="insert",
            position=position,
            text=value,
        ),
        session_token_hash=_token_hash(raw_token),
    )
    assert result["type"] == "note.ack"


def _token_hash(raw_token: str) -> str:
    return hash_token(raw_token, get_settings().token_pepper.get_secret_value())


def _headers(raw_token: str) -> dict[str, str]:
    return {
        "Authorization": f"Bearer {raw_token}",
        "X-Little-Orbit-Client": "android",
        "X-Little-Orbit-Version-Code": "19",
    }
