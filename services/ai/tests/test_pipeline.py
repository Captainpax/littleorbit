"""AI validation, quarantine, duplicate, and fallback tests."""

import json
from datetime import date

import httpx
import pytest

from little_orbit_ai.ollama import OllamaClient, OllamaFailure, OllamaSettings
from little_orbit_ai.pipeline import select_pool
from little_orbit_ai.safety import is_near_duplicate, validate_candidate
from little_orbit_ai.schemas import CandidateQuestion, Category, QuestionKind


def candidate(prompt: str) -> CandidateQuestion:
    return CandidateQuestion(
        client_id="candidate-1",
        kind=QuestionKind.FREE_TEXT,
        prompt=prompt,
        category=Category.CONNECTION,
        intimacy=False,
        options=[],
    )


def test_identifying_question_is_quarantined() -> None:
    result = validate_candidate(candidate("What is your partner's full legal name?"), [])
    assert not result.accepted
    assert "identifying_information" in result.reasons


def test_punctuation_and_case_do_not_defeat_duplicate_gate() -> None:
    assert is_near_duplicate("What made you smile today?", ["what made YOU smile today !"])


def test_curated_fallback_always_publishes_five_general_questions() -> None:
    result = select_pool(date(2026, 9, 11), None, [], OllamaSettings(), "ollama_unavailable")
    assert len(result.pool.general) == 5
    assert not any(item.intimacy for item in result.pool.general)
    assert result.pool.fallback_reason == "ollama_unavailable"


@pytest.mark.asyncio
async def test_pinned_model_generates_a_strict_batch() -> None:
    settings = OllamaSettings()
    requests: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request.url.path)
        if request.url.path == "/api/tags":
            return httpx.Response(
                200,
                json={"models": [{"name": settings.model, "digest": settings.manifest_digest}]},
            )
        request_payload = json.loads(request.content)
        assert isinstance(request_payload["format"], dict)
        assert request_payload["keep_alive"] == 0
        assert request_payload["options"]["num_ctx"] == 4096
        payload = {
            "schema_version": "1",
            "date": "2026-09-11",
            "questions": [
                {
                    "client_id": f"safe-{index}",
                    "kind": "free_text",
                    "prompt": f"What small moment would you enjoy sharing together number {index}?",
                    "category": "connection",
                    "intimacy": False,
                    "options": [],
                }
                for index in range(5)
            ],
        }
        return httpx.Response(200, json={"response": json.dumps(payload)})

    batch = await OllamaClient(settings, httpx.MockTransport(handler)).generate("safe prompt")

    assert len(batch.questions) == 5
    assert requests == ["/api/tags", "/api/generate"]


@pytest.mark.asyncio
async def test_changed_model_manifest_is_rejected_before_generation() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/api/tags"
        return httpx.Response(
            200,
            json={"models": [{"name": OllamaSettings().model, "digest": "sha256:changed"}]},
        )

    client = OllamaClient(OllamaSettings(), httpx.MockTransport(handler))
    with pytest.raises(OllamaFailure, match="pinned manifest"):
        await client.generate("Generate a safe batch")
