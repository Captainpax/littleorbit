"""AI validation, quarantine, duplicate, and fallback tests."""

import json
from datetime import date
from pathlib import Path

import httpx
import pytest

from little_orbit_ai.ollama import OllamaClient, OllamaFailure, OllamaSettings, _parse_batch
from little_orbit_ai.pipeline import select_pool
from little_orbit_ai.safety import is_near_duplicate, validate_candidate
from little_orbit_ai.schemas import CandidateQuestion, Category, IconKey, QuestionKind


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


@pytest.mark.parametrize(
    "prompt",
    [
        "What  small ritual helps you reconnect?",
        "What\t small ritual helps you reconnect?",
        "What\u00a0small ritual helps you reconnect?",
        " What small ritual helps you reconnect?",
    ],
)
def test_layout_whitespace_is_quarantined_without_repair(prompt: str) -> None:
    result = validate_candidate(candidate(prompt), [])

    assert not result.accepted
    assert "layout_whitespace" in result.reasons


def test_punctuation_and_case_do_not_defeat_duplicate_gate() -> None:
    assert is_near_duplicate("What made you smile today?", ["what made YOU smile today !"])


def test_partner_guess_is_written_to_both_people_not_about_a_third_person() -> None:
    unsafe = CandidateQuestion(
        client_id="candidate-guess",
        kind=QuestionKind.PARTNER_GUESS,
        prompt="What would your partner choose for a free evening?",
        category=Category.PLAYFUL,
        intimacy=False,
        options=["A movie", "A walk"],
        option_icons=[IconKey.MOVIE, IconKey.OUTDOORS],
    )

    result = validate_candidate(unsafe, [])

    assert not result.accepted
    assert "partner_guess_not_self_answerable" in result.reasons


def test_mismatched_intimacy_category_is_quarantined_per_candidate() -> None:
    mismatched = CandidateQuestion(
        client_id="candidate-intimacy",
        kind=QuestionKind.FREE_TEXT,
        prompt="What helps closeness feel comfortable for you?",
        category=Category.CONNECTION,
        intimacy=True,
        options=[],
    )

    result = validate_candidate(mismatched, [])

    assert not result.accepted
    assert "intimacy_category_mismatch" in result.reasons


def test_curated_fallback_always_publishes_five_general_questions() -> None:
    result = select_pool(date(2026, 9, 11), None, [], OllamaSettings(), "ollama_unavailable")
    assert len(result.pool.general) == 5
    assert not any(item.intimacy for item in result.pool.general)
    assert result.pool.fallback_reason == "ollama_unavailable"


def test_wrong_candidate_mix_is_recorded_without_discarding_valid_questions() -> None:
    fixture = Path(__file__).parents[3] / "protocol/fixtures/v2/question-batch.valid.json"
    payload = json.loads(fixture.read_text(encoding="utf-8"))
    payload["questions"][-1]["intimacy"] = False
    payload["questions"][-1]["category"] = "connection"

    batch = _parse_batch(payload)

    assert len(batch.questions) == 10
    assert batch.quarantined[0].reasons == ("candidate_mix_invalid",)


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
            "schema_version": "2",
            "date": "2026-09-11",
            "questions": [
                {
                    "client_id": f"safe-{index}",
                    "kind": "free_text",
                    "prompt": f"What small moment would you enjoy sharing together number {index}?",
                    "category": "intimacy" if index >= 8 else "connection",
                    "intimacy": index >= 8,
                    "options": [],
                    "option_icons": [],
                    "scale_low_label": None,
                    "scale_high_label": None,
                }
                for index in range(10)
            ],
        }
        return httpx.Response(200, json={"response": json.dumps(payload)})

    batch = await OllamaClient(settings, httpx.MockTransport(handler)).generate("safe prompt")

    assert len(batch.questions) == 10
    assert batch.quarantined == ()
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
