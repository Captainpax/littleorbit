"""Recovery delivery filters use real SQL without SMTP or a production database."""

from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from typing import Self
from unittest.mock import Mock

import pytest
from cryptography.fernet import Fernet
from pydantic import SecretStr, ValidationError
from sqlalchemy import ScalarResult, Select, create_engine
from sqlalchemy.orm import Session

from little_orbit_api import mail
from little_orbit_api.config import Settings
from little_orbit_api.models import MailOutbox

NOW = datetime(2026, 10, 21, 23, tzinfo=UTC)
CUTOFF = NOW - timedelta(hours=1)


class DeliverySession:
    """Run the actual selection through an isolated in-memory SQLite table."""

    def __init__(self, session: Session) -> None:
        self.session = session

    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(self, *args: object) -> None:
        pass

    async def scalars(self, statement: Select[tuple[MailOutbox]]) -> ScalarResult[MailOutbox]:
        return self.session.scalars(statement)

    async def commit(self) -> None:
        self.session.commit()


@pytest.fixture(autouse=True)
def isolated_settings(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setitem(Settings.model_config, "env_file", None)
    monkeypatch.delenv("RECOVERY_MAIL_NOT_BEFORE", raising=False)


@pytest.fixture
def delivery(monkeypatch: pytest.MonkeyPatch) -> Iterator[tuple[Session, Settings, Mock]]:
    engine = create_engine("sqlite:///:memory:")
    MailOutbox.metadata.tables["mail_outbox"].create(engine)
    with Session(engine, expire_on_commit=False) as session:
        settings = Settings(outbox_encryption_key=SecretStr(Fernet.generate_key().decode()))
        send = Mock()
        monkeypatch.setattr(mail, "SessionFactory", lambda: DeliverySession(session))
        monkeypatch.setattr(mail.SystemClock, "now", lambda self: NOW)
        monkeypatch.setattr(mail, "_send_smtp", send)
        yield session, settings, send
    engine.dispose()


def queued(session: Session, settings: Settings, created: datetime) -> MailOutbox:
    key = settings.outbox_encryption_key
    assert key is not None
    row = MailOutbox(
        recipient="synthetic@example.invalid",
        subject="Synthetic verification",
        encrypted_body=Fernet(key.get_secret_value().encode()).encrypt(b"private fixture").decode(),
        attempts=3,
        created_at=created,
        next_attempt_at=NOW - timedelta(minutes=1),
    )
    session.add(row)
    session.flush()
    return row


def state(row: MailOutbox) -> tuple[object, ...]:
    return row.encrypted_body, row.attempts, row.next_attempt_at, row.delivered_at, row.created_at


@pytest.mark.parametrize("cutoff", [CUTOFF, "2026-10-21T15:00:00-07:00"])
async def test_boundary_delivers_fresh_without_touching_or_decrypting_backlog(
    delivery: tuple[Session, Settings, Mock], cutoff: datetime | str, caplog: pytest.LogCaptureFixture
) -> None:
    session, settings, send = delivery
    settings = Settings.model_validate({
        "outbox_encryption_key": settings.outbox_encryption_key,
        "recovery_mail_not_before": cutoff,
    })
    held = [queued(session, settings, CUTOFF - timedelta(microseconds=1)) for _ in range(25)]
    # An old ciphertext that cannot decrypt must still remain unexamined.
    held[0].encrypted_body = "opaque-preserved-old-ciphertext"
    before = [state(row) for row in held]
    fresh = queued(session, settings, CUTOFF)
    await mail.deliver_pending_mail(settings, limit=1)
    assert [state(row) for row in held] == before
    assert fresh.delivered_at == NOW and fresh.encrypted_body == ""
    send.assert_called_once_with(settings, fresh, "private fixture")
    assert caplog.text == ""


async def test_unset_cutoff_preserves_original_delivery_behavior(
    delivery: tuple[Session, Settings, Mock],
) -> None:
    session, settings, send = delivery
    old = queued(session, settings, CUTOFF - timedelta(days=30))
    assert settings.recovery_mail_not_before is None
    await mail.deliver_pending_mail(settings)
    assert old.delivered_at == NOW and old.encrypted_body == ""
    send.assert_called_once()


async def test_future_cutoff_holds_all_existing_mail_without_rewriting_status(
    delivery: tuple[Session, Settings, Mock],
) -> None:
    session, settings, send = delivery
    row = queued(session, settings, NOW)
    before = state(row)
    settings = settings.model_copy(update={"recovery_mail_not_before": NOW + timedelta(days=1)})
    await mail.deliver_pending_mail(settings)
    assert state(row) == before
    send.assert_not_called()


async def test_cutoff_does_not_bypass_due_or_delivered_guards(
    delivery: tuple[Session, Settings, Mock],
) -> None:
    session, settings, send = delivery
    pending = queued(session, settings, NOW)
    pending.next_attempt_at = NOW + timedelta(minutes=1)
    delivered = queued(session, settings, NOW)
    delivered.delivered_at = NOW
    before = [state(pending), state(delivered)]
    settings = settings.model_copy(update={"recovery_mail_not_before": CUTOFF})
    await mail.deliver_pending_mail(settings)
    assert [state(pending), state(delivered)] == before
    send.assert_not_called()


@pytest.mark.parametrize("value", ["", "not-a-date", "2026-10-21", "2026-10-21T22:00:00", "0"])
def test_invalid_or_naive_environment_cutoff_refuses_settings(
    monkeypatch: pytest.MonkeyPatch, value: str,
) -> None:
    monkeypatch.setenv("RECOVERY_MAIL_NOT_BEFORE", value)
    with pytest.raises(ValidationError, match="aware ISO 8601"):
        Settings()


def test_aware_cutoff_normalizes_to_utc_and_rejects_non_instants() -> None:
    assert Settings.model_validate({"recovery_mail_not_before": "2026-10-21T15:00:00-07:00"}).recovery_mail_not_before == CUTOFF
    for value in (datetime(2026, 10, 21), 0, True):
        with pytest.raises(ValidationError, match="aware ISO 8601"):
            Settings.model_validate({"recovery_mail_not_before": value})
