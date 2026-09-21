"""Validation, fallback, replay, and route-contract checks for shared names."""

from datetime import UTC, datetime
from types import SimpleNamespace
from typing import cast
from uuid import uuid4

import pytest
from fastapi import HTTPException

from little_orbit_api.main import create_app
from little_orbit_api.profile_models import RelationshipNameOperation
from little_orbit_api.relationship_name_service import (
    _replay_result,
    normalize_assigned_name,
    safe_account_name,
)


@pytest.mark.parametrize(
    ("raw", "normalized"),
    [
        ("  Love Owl  ", "Love Owl"),
        ("Amélie", "Amélie"),
        ("Moon 🦉", "Moon 🦉"),
        ("Space 👩‍🚀", "Space 👩‍🚀"),
    ],
)
def test_friendly_unicode_names_are_normalized(raw: str, normalized: str) -> None:
    assert normalize_assigned_name(raw) == normalized


@pytest.mark.parametrize(
    "value",
    [
        "",
        "x" * 41,
        "two\nlines",
        "partner@example.com",
        "+1 (555) 123-4567",
        "https://example.com/name",
        "www.example.org",
    ],
)
def test_contact_and_control_data_is_rejected(value: str) -> None:
    with pytest.raises(ValueError):
        normalize_assigned_name(value)


def test_account_fallback_never_exposes_contact_information() -> None:
    assert safe_account_name("person@example.com", is_viewer=True) == "You"
    assert safe_account_name("person@example.com", is_viewer=False) == "Your partner"
    assert safe_account_name("Tristan", is_viewer=False) == "Tristan"


def test_replay_requires_the_same_scope_and_payload() -> None:
    couple_id = uuid4()
    subject_id = uuid4()
    now = datetime.now(UTC)
    operation = SimpleNamespace(
        couple_id=couple_id,
        subject_account_id=subject_id,
        request_hash="a" * 64,
        result_json={
            "display_name": "Owl",
            "assigned_name": "Owl",
            "revision": 1,
            "partner_assigned": True,
            "updated_at": now.isoformat(),
        },
    )

    result = _replay_result(
        cast(RelationshipNameOperation, operation), couple_id, subject_id, "a" * 64
    )
    assert result.display_name == "Owl"
    for wrong_couple, wrong_subject, wrong_hash in (
        (uuid4(), subject_id, "a" * 64),
        (couple_id, uuid4(), "a" * 64),
        (couple_id, subject_id, "b" * 64),
    ):
        with pytest.raises(HTTPException) as failure:
            _replay_result(
                cast(RelationshipNameOperation, operation),
                wrong_couple,
                wrong_subject,
                wrong_hash,
            )
        assert failure.value.status_code == 409


def test_partner_name_routes_are_explicit_and_typed() -> None:
    routes = {
        (getattr(route, "path", ""), tuple(getattr(route, "methods", ())))
        for route in create_app().routes
    }
    assert any(
        path == "/v1/couple/current/partner-name" and "PUT" in methods
        for path, methods in routes
    )
    assert any(
        path == "/v1/couple/current/partner-name/reset" and "POST" in methods
        for path, methods in routes
    )
