"""Validate every canonical cross-language fixture against JSON Schema."""

import json
from pathlib import Path

from jsonschema import Draft202012Validator, FormatChecker

ROOT = Path(__file__).resolve().parents[3]
SCHEMAS = ROOT / "protocol" / "schemas"
FIXTURES = ROOT / "protocol" / "fixtures"


def _validator(version: str, name: str) -> Draft202012Validator:
    path = SCHEMAS / version / f"{name}.schema.json"
    schema = json.loads(path.read_text(encoding="utf-8-sig"))
    return Draft202012Validator(schema, format_checker=FormatChecker())


def test_valid_protocol_fixtures_match_their_schema() -> None:
    """Every `.valid` example must pass its same-named versioned schema."""

    for version_dir in FIXTURES.glob("v*"):
        for fixture in version_dir.glob("*.valid.json"):
            name = fixture.name.removesuffix(".valid.json")
            payload = json.loads(fixture.read_text(encoding="utf-8-sig"))
            _validator(version_dir.name, name).validate(payload)


def test_invalid_protocol_fixtures_are_rejected() -> None:
    """Every `.invalid` example must fail at least one schema constraint."""

    for version_dir in FIXTURES.glob("v*"):
        for fixture in version_dir.glob("*.invalid.json"):
            name = fixture.name.removesuffix(".invalid.json")
            payload = json.loads(fixture.read_text(encoding="utf-8-sig"))
            assert list(_validator(version_dir.name, name).iter_errors(payload)), fixture.name
