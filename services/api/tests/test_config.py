"""Session-lifetime configuration checks."""

import pytest
from pydantic import ValidationError

from little_orbit_api.config import Settings


def test_app_and_admin_session_lifetimes_are_independent() -> None:
    """Keep mobile logins durable without extending owner-console sessions."""

    settings = Settings(session_minutes=43_200, admin_session_minutes=30)

    assert settings.session_minutes == 30 * 24 * 60
    assert settings.admin_session_minutes == 30


def test_session_lifetimes_reject_unsafe_bounds() -> None:
    """Reject accidental near-zero or unbounded session configuration."""

    with pytest.raises(ValidationError):
        Settings(session_minutes=1)
    with pytest.raises(ValidationError):
        Settings(admin_session_minutes=10_000)
