"""Bounded internal Ollama HTTP adapter."""

import json
from dataclasses import dataclass
from datetime import date
from typing import Any, cast

import httpx
from pydantic import TypeAdapter, ValidationError

from .schemas import CandidateQuestion, GeneratedBatch, GeneratedCandidate


@dataclass(frozen=True)
class OllamaSettings:
    """Pinned inference settings validated for the deployment GPU."""

    base_url: str = "http://ollama:11434"
    model: str = "qwen3:4b-instruct-2507-q4_K_M"
    manifest_digest: str = "0edcdef34593eac1aa2be9c7d06c432dcf81945adca5eca2f27662c18f168ba0"
    timeout_seconds: float = 120.0
    context_tokens: int = 4096
    output_tokens: int = 2400


class OllamaFailure(RuntimeError):
    """Bounded inference failure that should activate curated fallback."""


@dataclass(frozen=True)
class ModelCandidateFailure:
    """One model candidate rejected before content-safety validation."""

    client_id: str
    reasons: tuple[str, ...]


@dataclass(frozen=True)
class ParsedBatch:
    """A valid generation envelope with candidate-level failures quarantined."""

    date: date
    questions: tuple[CandidateQuestion, ...]
    quarantined: tuple[ModelCandidateFailure, ...]


class OllamaClient:
    """Call internal Ollama once and parse its untrusted JSON response."""

    def __init__(self, settings: OllamaSettings, transport: httpx.AsyncBaseTransport | None = None):
        self._settings = settings
        self._transport = transport

    async def generate(self, prompt: str) -> ParsedBatch:
        """Generate a strict batch or raise a quarantine-worthy failure."""

        request = {
            "model": self._settings.model,
            "prompt": prompt,
            "stream": False,
            # Ollama forwards this schema to the constrained decoder. Validation below
            # remains mandatory because model output is always an untrusted boundary.
            "format": GeneratedBatch.model_json_schema(),
            "keep_alive": 0,
            "options": {
                "num_ctx": self._settings.context_tokens,
                "num_predict": self._settings.output_tokens,
                "temperature": 0.8,
                "top_p": 0.9,
            },
        }
        timeout = httpx.Timeout(self._settings.timeout_seconds)
        try:
            async with httpx.AsyncClient(
                base_url=self._settings.base_url, timeout=timeout, transport=self._transport
            ) as client:
                # Check the immutable digest before inference so a reused mutable tag
                # cannot silently change the reviewed model behind this configuration.
                await self._require_pinned_model(client)
                response = await client.post("/api/generate", json=request)
                response.raise_for_status()
                envelope = response.json()
                payload = json.loads(envelope["response"])
                return _parse_batch(payload)
        except (httpx.HTTPError, KeyError, TypeError, ValueError) as exc:
            # Collapse untrusted transport and envelope details into one bounded
            # failure type; the caller can fall back without publishing partial data.
            raise OllamaFailure(
                "Ollama response failed transport or strict schema validation"
            ) from exc

    async def _require_pinned_model(self, client: httpx.AsyncClient) -> None:
        """Reject a mutable tag whose installed manifest is not the reviewed build."""

        response = await client.get("/api/tags")
        response.raise_for_status()
        models = response.json().get("models", [])
        installed = next(
            (item for item in models if item.get("name") == self._settings.model), None
        )
        if installed is None or installed.get("digest") != self._settings.manifest_digest:
            raise OllamaFailure("Installed Ollama model does not match the pinned manifest digest")


def _parse_batch(payload: object) -> ParsedBatch:
    """Validate one envelope and quarantine structurally invalid candidates."""

    target, raw_questions = _validate_envelope(payload)
    adapter: TypeAdapter[GeneratedCandidate] = TypeAdapter(GeneratedCandidate)
    questions: list[CandidateQuestion] = []
    quarantined: list[ModelCandidateFailure] = []
    intimacy_count = sum(
        isinstance(item, dict) and item.get("intimacy") is True for item in raw_questions
    )
    if intimacy_count != 2:
        # Preserve valid individual candidates, but retain batch-level evidence that
        # the model missed the requested general/intimacy mix.
        quarantined.append(ModelCandidateFailure("batch", ("candidate_mix_invalid",)))
    for index, item in enumerate(raw_questions):
        try:
            questions.append(adapter.validate_python(item))
        except ValidationError:
            # Quarantine candidates independently so one malformed sibling does not
            # discard safe candidates that can reduce curated fallback usage.
            quarantined.append(
                ModelCandidateFailure(_safe_client_id(item, index), ("schema_validation_failed",))
            )
    return ParsedBatch(target, tuple(questions), tuple(quarantined))


def _validate_envelope(payload: object) -> tuple[date, list[object]]:
    """Validate fields that make a generation response one atomic batch."""

    if not isinstance(payload, dict) or set(payload) != {"schema_version", "date", "questions"}:
        raise ValueError("generation envelope has unexpected fields")
    values = cast(dict[str, Any], payload)
    if values["schema_version"] != "2":
        raise ValueError("generation envelope uses an unsupported schema version")
    date_value = values["date"]
    if not isinstance(date_value, str):
        raise ValueError("generation envelope date must be an ISO date")
    target = date.fromisoformat(date_value)
    raw_questions = values["questions"]
    if not isinstance(raw_questions, list) or len(raw_questions) != 10:
        raise ValueError("generation envelope must contain exactly ten candidates")
    return target, cast(list[object], raw_questions)


def _safe_client_id(item: object, index: int) -> str:
    """Return a bounded diagnostic identifier without retaining malformed content."""

    # Never derive a diagnostic label from prompts or options: quarantine metadata
    # must remain content-free even when the candidate cannot be parsed safely.
    value = item.get("client_id") if isinstance(item, dict) else None
    return value if isinstance(value, str) and 3 <= len(value) <= 48 else f"candidate-{index + 1}"
