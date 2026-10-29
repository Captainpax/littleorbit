"""SMTP verification and ordering tests; no socket or real credential is used."""

import ssl
from unittest.mock import Mock

import pytest
from pydantic import SecretStr

from little_orbit_api import mail
from little_orbit_api.config import Settings
from little_orbit_api.models import MailOutbox


@pytest.fixture(autouse=True)
def isolated_settings(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setitem(Settings.model_config, "env_file", None)


def settings(**overrides: object) -> Settings:
    """Explicit synthetic settings, never discovered from a production env file."""
    return Settings.model_validate({"smtp_host": "smtp.example.invalid", "smtp_port": 587,
        "smtp_starttls": True, "smtp_username": "synthetic", "smtp_password": SecretStr("unused"),
        **overrides})


def row() -> MailOutbox:
    return MailOutbox(recipient="synthetic@example.invalid", subject="Fixture")


def transport(monkeypatch: pytest.MonkeyPatch) -> tuple[Mock, Mock]:
    connection = Mock()
    factory = Mock()
    factory.return_value.__enter__ = Mock(return_value=connection)
    factory.return_value.__exit__ = Mock(return_value=False)
    monkeypatch.setattr(mail.smtplib, "SMTP", factory)
    return factory, connection


def test_verified_tls_precedes_authentication_and_delivery(monkeypatch: pytest.MonkeyPatch) -> None:
    factory, smtp = transport(monkeypatch)
    mail._send_smtp(settings(), row(), "Synthetic fixture")
    factory.assert_called_once_with("smtp.example.invalid", 587, timeout=20)
    context = smtp.starttls.call_args.kwargs["context"]
    assert context.verify_mode == ssl.CERT_REQUIRED and context.check_hostname
    assert [call[0] for call in smtp.method_calls] == ["starttls", "login", "send_message"]


@pytest.mark.parametrize("overrides", [
    {"smtp_starttls": False}, {"smtp_password": None}, {"smtp_username": None},
])
def test_unsafe_credentials_refuse_before_connect(
    monkeypatch: pytest.MonkeyPatch, overrides: dict[str, object],
) -> None:
    factory, _ = transport(monkeypatch)
    with pytest.raises(ValueError, match="Credentialed SMTP requires"):
        mail._send_smtp(settings(**overrides), row(), "Synthetic fixture")
    factory.assert_not_called()


@pytest.mark.parametrize("failure", [ssl.SSLCertVerificationError("fixture"),
                                     mail.smtplib.SMTPNotSupportedError("fixture")])
def test_tls_failure_never_authenticates_or_sends(
    monkeypatch: pytest.MonkeyPatch, failure: Exception,
) -> None:
    _, smtp = transport(monkeypatch)
    smtp.starttls.side_effect = failure
    with pytest.raises(type(failure)):
        mail._send_smtp(settings(), row(), "Synthetic fixture")
    smtp.login.assert_not_called()
    smtp.send_message.assert_not_called()


def test_plaintext_development_without_credentials_is_unchanged(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _, smtp = transport(monkeypatch)
    mail._send_smtp(settings(smtp_username=None, smtp_password=None, smtp_starttls=False),
                    row(), "Synthetic fixture")
    smtp.starttls.assert_not_called()
    smtp.login.assert_not_called()
    smtp.send_message.assert_called_once()
