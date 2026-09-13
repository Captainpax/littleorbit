"""Privacy and contract checks for the couple activity feed."""

from datetime import UTC, datetime
from uuid import uuid4

import pytest
from pydantic import ValidationError

from little_orbit_api.activity_models import ActivityEvent
from little_orbit_api.activity_schemas import ActivityResponse, ActivitySeenRequest
from little_orbit_api.routes.activity import _response


def test_activity_response_contains_no_relationship_content() -> None:
    """Rendered events expose routing metadata without feature content."""

    viewer_id = uuid4()
    event = ActivityEvent(
        id=uuid4(), couple_id=uuid4(), actor_id=viewer_id, sequence=7,
        dedupe_key="note:create:fixture", kind="note_created", target_type="note",
        target_id=uuid4(), target_title="Weekend ideas", emoji=None,
        created_at=datetime.now(UTC),
    )

    rendered = _response(event, "Private name", viewer_id, 6).model_dump()

    assert rendered["partner_display_name"] == "You"
    assert rendered["seen"] is False
    assert not ({"body", "answer", "location", "file_name"} & rendered.keys())


def test_activity_contract_rejects_content_and_negative_watermarks() -> None:
    """Clients cannot inject private content or move a watermark below zero."""

    with pytest.raises(ValidationError):
        ActivitySeenRequest(through_sequence=-1, operation_id=uuid4())
    with pytest.raises(ValidationError):
        ActivityResponse.model_validate({
            "id": uuid4(), "sequence": 1, "kind": "note_created",
            "partner_display_name": "Partner", "target_type": None, "target_id": None,
            "target_title": None, "emoji": None, "created_at": datetime.now(UTC),
            "seen": False, "body": "must not cross the activity boundary",
        })
