"""Email-link privacy behavior."""

from little_orbit_api.config import Settings
from little_orbit_api.mail import recovery_body, verification_body


def test_one_use_tokens_stay_out_of_http_request_urls() -> None:
    settings = Settings(public_base_url="https://lil-orb.pax-kun.com")
    token = "private-one-use-token"

    verification = verification_body(settings, "Orbit", token)
    recovery = recovery_body(settings, "Orbit", token)

    assert f"/verify-email#token={token}" in verification
    assert f"/reset-password#token={token}" in recovery
    assert "?token=" not in verification
    assert "?token=" not in recovery
