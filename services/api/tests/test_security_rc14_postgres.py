"""Optional PostgreSQL integration tests for RC14 transaction boundaries."""

import asyncio
import os
from datetime import UTC, date, datetime, timedelta
from urllib.parse import parse_qs, urlparse
from uuid import UUID, uuid4

import httpx
import pyotp
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
from little_orbit_api.models import (  # noqa: E402
    Account,
    AdminMfa,
    Couple,
    CoupleMember,
    DeletionJob,
    Note,
    OneUseToken,
    PairCode,
    Question,
    QuizAnswer,
    RateLimitBucket,
    Session,
)
from little_orbit_api.note_edit_service import (  # noqa: E402
    NoteAccessRevoked,
    NoteEditMessage,
    apply_note_edit,
)
from little_orbit_api.rate_limit import (  # noqa: E402
    RateLimitRule,
    consume_rate_limits,
    purge_rate_limit_state,
)
from little_orbit_api.security import (  # noqa: E402
    encrypt_totp_secret,
    hash_password,
    hash_token,
)


@pytest_asyncio.fixture(autouse=True, loop_scope="session")
async def clean_database() -> None:
    """Keep every test isolated from other tests and all non-test databases."""

    async with engine.begin() as connection:
        existing = set(await connection.run_sync(lambda sync: inspect(sync).get_table_names()))
        quote = connection.dialect.identifier_preparer.quote
        tables = ", ".join(
            quote(table.name) for table in Base.metadata.sorted_tables if table.name in existing
        )
        await connection.execute(text(f"TRUNCATE TABLE {tables} RESTART IDENTITY CASCADE"))


def _account(email: str, *, admin: bool = False, suspended: bool = False) -> Account:
    now = datetime.now(UTC)
    return Account(
        id=uuid4(),
        email_normalized=email,
        password_hash=hash_password("valid-password-123"),
        display_name=email.split("@", 1)[0],
        is_adult=True,
        accepted_terms_version="2026-09-10",
        verified_at=now,
        suspended_at=now if suspended else None,
        is_admin=admin,
        created_at=now,
        updated_at=now,
    )


def _session(account_id: UUID, raw_token: str, *, revoked: bool = False) -> Session:
    now = datetime.now(UTC)
    return Session(
        account_id=account_id,
        token_hash=hash_token(raw_token, get_settings().token_pepper.get_secret_value()),
        expires_at=now + timedelta(hours=1),
        revoked_at=now if revoked else None,
        authenticated_at=now,
        created_at=now,
    )


async def test_postgres_rate_counter_caps_and_expires() -> None:
    now = datetime.now(UTC)
    rule = RateLimitRule("test-login:ip", "203.0.113.9", 2, timedelta(minutes=15))

    decisions = await asyncio.gather(
        *(consume_rate_limits([rule], now=now, settings=get_settings()) for _ in range(4))
    )

    assert sum(item.allowed for item in decisions) == 2
    async with SessionFactory() as session:
        assert await session.scalar(select(RateLimitBucket.count)) == 3
    reset = await consume_rate_limits(
        [rule], now=now + timedelta(minutes=16), settings=get_settings()
    )
    assert reset.allowed
    async with SessionFactory() as session:
        await purge_rate_limit_state(session, now + timedelta(days=2))
        await session.commit()
        assert await session.scalar(select(func.count()).select_from(RateLimitBucket)) == 0


async def test_password_reset_consumes_all_tokens_and_rejects_deleted_login() -> None:
    account = _account("reset@example.com")
    deleted = _account("deleted@example.com")
    deleted.deleted_at = datetime.now(UTC)
    selected = "a" * 40
    other = "b" * 40
    now = datetime.now(UTC)
    old_session = _session(account.id, "s" * 40)
    async with SessionFactory() as session:
        session.add_all([account, deleted, old_session])
        session.add_all(
            [
                OneUseToken(
                    account_id=account.id,
                    purpose="password_reset",
                    token_hash=hash_token(raw, get_settings().token_pepper.get_secret_value()),
                    expires_at=now + timedelta(minutes=30),
                    created_at=now,
                )
                for raw in (selected, other)
            ]
        )
        await session.commit()

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=create_app()), base_url="http://localhost"
    ) as client:
        response = await client.post(
            "/v1/auth/reset-password",
            json={"token": selected, "password": "replacement-password-123"},
        )
        deleted_login = await client.post(
            "/v1/auth/login",
            json={"email": deleted.email_normalized, "password": "valid-password-123"},
        )

    assert response.status_code == 200
    assert deleted_login.status_code == 401
    async with SessionFactory() as session:
        tokens = list(await session.scalars(select(OneUseToken)))
        stored_session = await session.get(Session, old_session.id)
        assert tokens and all(item.consumed_at is not None for item in tokens)
        assert stored_session is not None and stored_session.revoked_at is not None


async def test_password_reset_and_rotation_cannot_leave_a_live_session() -> None:
    """Whichever account-locked request wins, reset leaves no surviving session."""

    account = _account("reset-race@example.com")
    bearer = "r" * 40
    reset_token = "t" * 40
    now = datetime.now(UTC)
    async with SessionFactory() as session:
        session.add_all([account, _session(account.id, bearer)])
        session.add(
            OneUseToken(
                account_id=account.id,
                purpose="password_reset",
                token_hash=hash_token(reset_token, get_settings().token_pepper.get_secret_value()),
                expires_at=now + timedelta(minutes=30),
                created_at=now,
            )
        )
        await session.commit()

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=create_app()), base_url="http://localhost"
    ) as client:
        reset_response, rotate_response = await asyncio.gather(
            client.post(
                "/v1/auth/reset-password",
                json={"token": reset_token, "password": "replacement-password-123"},
            ),
            client.post(
                "/v1/auth/session/rotate",
                headers={"Authorization": f"Bearer {bearer}"},
            ),
        )

    assert reset_response.status_code == 200
    assert rotate_response.status_code in {200, 401}
    async with SessionFactory() as session:
        active = await session.scalar(
            select(func.count())
            .select_from(Session)
            .where(Session.account_id == account.id, Session.revoked_at.is_(None))
        )
        assert active == 0


async def _seed_enrolled_admin(bearer: str, recovery: str) -> None:
    settings = get_settings()
    assert settings.totp_encryption_key is not None
    now = datetime.now(UTC)
    admin = _account("admin@example.com", admin=True)
    current_secret = pyotp.random_base32()
    async with SessionFactory() as session:
        session.add_all(
            [
                admin,
                _session(admin.id, bearer),
                AdminMfa(
                    account_id=admin.id,
                    encrypted_secret=encrypt_totp_secret(
                        current_secret, settings.totp_encryption_key.get_secret_value()
                    ),
                    recovery_hashes=[
                        hash_token(recovery, settings.token_pepper.get_secret_value())
                    ],
                    enabled_at=now,
                    created_at=now,
                    updated_at=now,
                ),
            ]
        )
        await session.commit()


async def _replace_admin_factor(
    bearer: str, recovery: str
) -> tuple[httpx.Response, httpx.Response, httpx.Response, httpx.Response]:
    headers = {"Authorization": f"Bearer {bearer}"}
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=create_app()), base_url="http://localhost"
    ) as client:
        rejected = await client.post(
            "/v2/admin/mfa/start",
            headers=headers,
            json={"password": "valid-password-123"},
        )
        started = await client.post(
            "/v2/admin/mfa/start",
            headers=headers,
            json={"password": "valid-password-123", "current_recovery_code": recovery},
        )
        secret = parse_qs(urlparse(started.json()["otpauth_uri"]).query)["secret"][0]
        confirmed = await client.post(
            "/v2/admin/mfa/confirm",
            headers=headers,
            json={"code": pyotp.TOTP(secret).now()},
        )
        config = await client.get(
            "/v2/admin/configuration",
            headers={"Authorization": f"Bearer {confirmed.json()['access_token']}"},
        )
    return rejected, started, confirmed, config


async def test_mfa_replacement_needs_old_factor_then_revokes_sessions() -> None:
    settings = get_settings()
    bearer = "c" * 40
    recovery = "current-recovery-code"
    await _seed_enrolled_admin(bearer, recovery)
    rejected, started, confirmed, config = await _replace_admin_factor(bearer, recovery)

    assert rejected.status_code == 401
    assert started.status_code == 200
    assert confirmed.status_code == 200
    assert config.status_code == 403
    serialized = config.text
    assert "database_url" not in serialized
    assert "token_pepper" not in serialized
    assert "private-password" not in serialized
    async with SessionFactory() as session:
        old = await session.scalar(
            select(Session).where(
                Session.token_hash == hash_token(bearer, settings.token_pepper.get_secret_value())
            )
        )
        assert old is not None and old.revoked_at is not None


async def test_suspended_pending_partner_cannot_be_confirmed() -> None:
    creator = _account("creator@example.com")
    partner = _account("partner@example.com", suspended=True)
    bearer = "d" * 40
    now = datetime.now(UTC)
    request_id = uuid4()
    async with SessionFactory() as session:
        session.add_all([creator, partner, _session(creator.id, bearer)])
        session.add(
            PairCode(
                id=request_id,
                creator_id=creator.id,
                code_hash="e" * 64,
                pending_partner_id=partner.id,
                expires_at=now + timedelta(minutes=10),
                created_at=now,
            )
        )
        await session.commit()

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=create_app()), base_url="http://localhost"
    ) as client:
        response = await client.post(
            "/v1/pairing/confirm",
            headers={"Authorization": f"Bearer {bearer}"},
            json={"request_id": str(request_id)},
        )

    assert response.status_code == 400
    async with SessionFactory() as session:
        assert await session.scalar(select(func.count()).select_from(Couple)) == 0


async def _seed_competing_pair_requests() -> tuple[UUID, str, UUID, str]:
    """Create two pending relationships that share one intended partner."""

    first = _account("first@example.com")
    shared = _account("shared@example.com")
    second = _account("second@example.com")
    first_bearer = "h" * 40
    second_bearer = "i" * 40
    first_request = uuid4()
    second_request = uuid4()
    now = datetime.now(UTC)
    async with SessionFactory() as session:
        session.add_all(
            [
                first,
                shared,
                second,
                _session(first.id, first_bearer),
                _session(second.id, second_bearer),
                PairCode(
                    id=first_request,
                    creator_id=first.id,
                    pending_partner_id=shared.id,
                    code_hash="2" * 64,
                    expires_at=now + timedelta(minutes=10),
                    created_at=now,
                ),
                PairCode(
                    id=second_request,
                    creator_id=second.id,
                    pending_partner_id=shared.id,
                    code_hash="3" * 64,
                    expires_at=now + timedelta(minutes=10),
                    created_at=now,
                ),
            ]
        )
        await session.commit()
    return first_request, first_bearer, second_request, second_bearer


async def test_competing_pair_confirmations_create_one_relationship() -> None:
    """Stable account locks keep one account out of two simultaneous couples."""

    (
        first_request,
        first_bearer,
        second_request,
        second_bearer,
    ) = await _seed_competing_pair_requests()

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=create_app()), base_url="http://localhost"
    ) as client:
        responses = await asyncio.gather(
            client.post(
                "/v1/pairing/confirm",
                headers={"Authorization": f"Bearer {first_bearer}"},
                json={"request_id": str(first_request)},
            ),
            client.post(
                "/v1/pairing/confirm",
                headers={"Authorization": f"Bearer {second_bearer}"},
                json={"request_id": str(second_request)},
            ),
        )

    assert sorted(response.status_code for response in responses) == [200, 409]
    async with SessionFactory() as session:
        assert await session.scalar(select(func.count()).select_from(Couple)) == 1
        active_members = await session.scalar(
            select(func.count()).select_from(CoupleMember).where(CoupleMember.left_at.is_(None))
        )
        assert active_members == 2


async def test_unpair_and_deletion_share_one_terminal_relationship_state() -> None:
    """Concurrent privacy exits must end sharing and schedule deletion once."""

    actor = _account("leaving@example.com")
    partner = _account("staying@example.com")
    bearer = "j" * 40
    now = datetime.now(UTC)
    couple = Couple(id=uuid4(), created_at=now, updated_at=now, proximity_threshold_m=100)
    async with SessionFactory() as session:
        session.add_all([actor, partner, couple, _session(actor.id, bearer)])
        session.add_all(
            [
                CoupleMember(couple_id=couple.id, account_id=item.id, joined_at=now)
                for item in (actor, partner)
            ]
        )
        await session.commit()

    headers = {"Authorization": f"Bearer {bearer}"}
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=create_app()), base_url="http://localhost"
    ) as client:
        unpair_response, deletion_response = await asyncio.gather(
            client.post("/v1/couple/unpair", headers=headers),
            client.post(
                "/v1/account/deletion",
                headers=headers,
                json={"password": "valid-password-123"},
            ),
        )

    assert deletion_response.status_code == 200
    assert unpair_response.status_code in {200, 401, 409}
    async with SessionFactory() as session:
        stored_actor = await session.get(Account, actor.id)
        stored_couple = await session.get(Couple, couple.id)
        assert stored_actor is not None and stored_actor.deleted_at is not None
        assert stored_couple is not None and stored_couple.ended_at is not None
        assert await session.scalar(select(func.count()).select_from(DeletionJob)) == 1
        active_members = await session.scalar(
            select(func.count())
            .select_from(CoupleMember)
            .where(CoupleMember.couple_id == couple.id, CoupleMember.left_at.is_(None))
        )
        assert active_members == 0


async def test_export_hides_legacy_answers_until_both_submit() -> None:
    left = _account("left@example.com")
    right = _account("right@example.com")
    bearer = "f" * 40
    now = datetime.now(UTC)
    couple = Couple(id=uuid4(), created_at=now, updated_at=now, proximity_threshold_m=100)
    question = Question(
        id=uuid4(),
        publish_date=date.today(),
        kind="free_text",
        prompt="What made today feel special?",
        category="everyday",
        options=[],
        source="curated",
        normalized_hash="1" * 64,
    )
    async with SessionFactory() as session:
        session.add_all([left, right, couple, question, _session(left.id, bearer)])
        session.add_all(
            [
                CoupleMember(couple_id=couple.id, account_id=item.id, joined_at=now)
                for item in (left, right)
            ]
        )
        session.add(
            QuizAnswer(
                question_id=question.id,
                couple_id=couple.id,
                account_id=left.id,
                answer={"text": "Private"},
                submitted_at=now,
            )
        )
        await session.commit()

    app = create_app()
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://localhost"
    ) as client:
        hidden = await client.get(
            "/v1/account/export", headers={"Authorization": f"Bearer {bearer}"}
        )
        async with SessionFactory() as session:
            session.add(
                QuizAnswer(
                    question_id=question.id,
                    couple_id=couple.id,
                    account_id=right.id,
                    answer={"text": "Shared"},
                    submitted_at=now,
                )
            )
            await session.commit()
        revealed = await client.get(
            "/v1/account/export", headers={"Authorization": f"Bearer {bearer}"}
        )

    assert hidden.status_code == 200
    assert hidden.json()["data"]["relationships"][0]["quiz_answers"] == []
    assert len(revealed.json()["data"]["relationships"][0]["quiz_answers"]) == 2


async def test_revoked_session_cannot_apply_note_operation() -> None:
    left = _account("writer@example.com")
    right = _account("reader@example.com")
    raw_token = "g" * 40
    now = datetime.now(UTC)
    couple = Couple(id=uuid4(), created_at=now, updated_at=now, proximity_threshold_m=100)
    note = Note(
        id=uuid4(),
        creation_operation_id=uuid4(),
        couple_id=couple.id,
        title="Private note",
        body="",
        revision=0,
        metadata_revision=0,
        created_at=now,
        updated_at=now,
    )
    stored_session = _session(left.id, raw_token, revoked=True)
    async with SessionFactory() as session:
        session.add_all([left, right, couple, note, stored_session])
        session.add_all(
            [
                CoupleMember(couple_id=couple.id, account_id=item.id, joined_at=now)
                for item in (left, right)
            ]
        )
        await session.commit()

    with pytest.raises(NoteAccessRevoked):
        await apply_note_edit(
            note.id,
            left.id,
            NoteEditMessage(
                operation_id=uuid4(), base_revision=0, kind="insert", position=0, text="x"
            ),
            session_token_hash=stored_session.token_hash,
        )
