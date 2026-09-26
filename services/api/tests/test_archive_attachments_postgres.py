"""PostgreSQL authorization tests for former-pairing attachment archives."""

import hashlib
import os
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace
from uuid import UUID, uuid4

import httpx
import pytest
import pytest_asyncio
from sqlalchemy import inspect, text

pytestmark = [
    pytest.mark.skipif(
        not os.getenv("LITTLE_ORBIT_TEST_DATABASE_URL"),
        reason="set LITTLE_ORBIT_TEST_DATABASE_URL to an isolated PostgreSQL database",
    ),
    pytest.mark.asyncio(loop_scope="session"),
]

from little_orbit_api.attachment_models import NoteAttachment  # noqa: E402
from little_orbit_api.attachment_storage import available_path  # noqa: E402
from little_orbit_api.config import get_settings  # noqa: E402
from little_orbit_api.database import Base, SessionFactory, engine  # noqa: E402
from little_orbit_api.main import create_app  # noqa: E402
from little_orbit_api.models import (  # noqa: E402
    Account,
    Couple,
    CoupleMember,
    Note,
    Session,
)
from little_orbit_api.routes import archive_attachments  # noqa: E402
from little_orbit_api.security import hash_password, hash_token  # noqa: E402


@pytest_asyncio.fixture(autouse=True, loop_scope="session")
async def clean_database() -> None:
    """Keep the archive test isolated from every non-test database."""

    async with engine.begin() as connection:
        existing = set(await connection.run_sync(lambda sync: inspect(sync).get_table_names()))
        quote = connection.dialect.identifier_preparer.quote
        tables = ", ".join(
            quote(table.name) for table in Base.metadata.sorted_tables if table.name in existing
        )
        await connection.execute(text(f"TRUNCATE TABLE {tables} RESTART IDENTITY CASCADE"))


def _account(email: str, now: datetime) -> Account:
    return Account(
        id=uuid4(),
        email_normalized=email,
        password_hash=hash_password("archive-test-password"),
        display_name=email.split("@", 1)[0],
        is_adult=True,
        accepted_terms_version="2026-09-10",
        verified_at=now,
        created_at=now,
        updated_at=now,
    )


def _login(account_id: UUID, token: str, now: datetime) -> Session:
    return Session(
        account_id=account_id,
        token_hash=hash_token(token, get_settings().token_pepper.get_secret_value()),
        expires_at=now + timedelta(hours=1),
        authenticated_at=now,
        created_at=now,
    )


async def _seed_archive(root: Path) -> tuple[UUID, UUID, NoteAttachment, str, str]:
    now = datetime.now(UTC)
    ended = now - timedelta(minutes=5)
    owner = _account("archive-owner@example.com", now)
    partner = _account("archive-partner@example.com", now)
    outsider = _account("archive-outsider@example.com", now)
    owner_token, outsider_token = "o" * 40, "x" * 40
    couple = _ended_couple(now, ended)
    note = _archive_note(couple.id, now, ended)
    content = b"sanitized archive bytes"
    clean, pending = _archive_files(note, couple, owner, now, ended, content)
    path = available_path(root, clean.storage_key)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)
    await _persist_archive(
        now,
        ended,
        owner,
        partner,
        outsider,
        couple,
        note,
        clean,
        pending,
        owner_token,
        outsider_token,
    )
    return couple.id, note.id, clean, owner_token, outsider_token


def _ended_couple(now: datetime, ended: datetime) -> Couple:
    return Couple(
        id=uuid4(),
        ended_at=ended,
        created_at=now - timedelta(days=3),
        updated_at=ended,
        proximity_threshold_m=100,
    )


def _archive_note(couple_id: UUID, now: datetime, ended: datetime) -> Note:
    return Note(
        id=uuid4(),
        creation_operation_id=uuid4(),
        couple_id=couple_id,
        title="Trip memories",
        body="A private archived note",
        revision=2,
        metadata_revision=1,
        created_at=now - timedelta(days=2),
        updated_at=ended,
    )


def _archive_files(
    note: Note,
    couple: Couple,
    owner: Account,
    now: datetime,
    ended: datetime,
    content: bytes,
) -> tuple[NoteAttachment, NoteAttachment]:
    clean = NoteAttachment(
        id=uuid4(),
        note_id=note.id,
        couple_id=couple.id,
        uploaded_by=owner.id,
        operation_id=uuid4(),
        file_name="memory.txt",
        media_type="text/plain",
        size_bytes=len(content),
        uploaded_bytes=len(content),
        sha256=hashlib.sha256(content).hexdigest(),
        storage_key=uuid4().hex,
        status="available",
        created_at=now - timedelta(days=1),
        updated_at=ended,
        scanned_at=ended,
    )
    pending = NoteAttachment(
        id=uuid4(),
        note_id=note.id,
        couple_id=couple.id,
        uploaded_by=owner.id,
        operation_id=uuid4(),
        file_name="not-ready.txt",
        media_type="text/plain",
        size_bytes=1,
        uploaded_bytes=1,
        sha256=hashlib.sha256(b"x").hexdigest(),
        storage_key=uuid4().hex,
        status="pending_scan",
        created_at=now,
        updated_at=now,
    )
    return clean, pending


async def _persist_archive(
    now: datetime,
    ended: datetime,
    owner: Account,
    partner: Account,
    outsider: Account,
    couple: Couple,
    note: Note,
    clean: NoteAttachment,
    pending: NoteAttachment,
    owner_token: str,
    outsider_token: str,
) -> None:
    async with SessionFactory() as session:
        session.add_all([owner, partner, outsider, couple])
        await session.flush()
        session.add(note)
        session.add_all(
            [
                CoupleMember(
                    couple_id=couple.id,
                    account_id=account.id,
                    joined_at=now - timedelta(days=3),
                    left_at=ended,
                )
                for account in (owner, partner)
            ]
        )
        session.add_all(
            [_login(owner.id, owner_token, now), _login(outsider.id, outsider_token, now)]
        )
        await session.flush()
        session.add_all([clean, pending])
        await session.commit()


async def test_archive_files_are_read_only_and_former_member_private(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A former member sees clean bytes while every unauthorized lookup looks identical."""

    archive_id, note_id, attachment, owner_token, outsider_token = await _seed_archive(tmp_path)
    monkeypatch.setattr(
        archive_attachments,
        "get_settings",
        lambda: SimpleNamespace(attachment_storage_dir=tmp_path),
    )
    base = f"/v1/couple/archives/{archive_id}/notes/{note_id}/attachments"
    owner_header = {"Authorization": f"Bearer {owner_token}"}
    outsider_header = {"Authorization": f"Bearer {outsider_token}"}
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=create_app()), base_url="http://localhost"
    ) as client:
        detail = await client.get(f"/v1/couple/archives/{archive_id}", headers=owner_header)
        listing = await client.get(base, headers=owner_header)
        download = await client.get(f"{base}/{attachment.id}/content", headers=owner_header)
        head = await client.head(f"{base}/{attachment.id}/content", headers=owner_header)
        unknown_note = await client.get(
            f"/v1/couple/archives/{archive_id}/notes/{uuid4()}/attachments",
            headers=owner_header,
        )
        outsider = await client.get(base, headers=outsider_header)
        outsider_file = await client.get(f"{base}/{attachment.id}/content", headers=outsider_header)
        active_route = await client.get(
            f"/v1/notes/{note_id}/attachments/{attachment.id}/content", headers=owner_header
        )
        mutation = await client.delete(f"{base}/{attachment.id}", headers=owner_header)

    assert detail.status_code == 200
    assert len(detail.json()["notes"][0]["attachments"]) == 1
    assert listing.status_code == 200
    assert [item["id"] for item in listing.json()] == [str(attachment.id)]
    assert download.status_code == 200 and download.content == b"sanitized archive bytes"
    assert download.headers["cache-control"] == "private, no-store"
    assert download.headers["x-content-type-options"] == "nosniff"
    assert head.status_code == 200 and int(head.headers["content-length"]) == attachment.size_bytes
    assert unknown_note.status_code == outsider.status_code == outsider_file.status_code == 404
    assert unknown_note.json() == outsider.json() == outsider_file.json()
    assert active_route.status_code == 409
    assert active_route.json()["detail"]["code"] == "relationship_inactive"
    assert mutation.status_code == 404
