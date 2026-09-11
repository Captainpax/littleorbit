"""Bounded internal Ollama HTTP adapter."""

import json
from dataclasses import dataclass

import httpx

from .schemas import GeneratedBatch


@dataclass(frozen=True)
class OllamaSettings:
    """Pinned inference settings validated for the deployment GPU."""

    base_url: str = "http://ollama:11434"
    model: str = "qwen3:4b-instruct-2507-q4_K_M"
    manifest_digest: str = "0edcdef34593eac1aa2be9c7d06c432dcf81945adca5eca2f27662c18f168ba0"
    timeout_seconds: float = 90.0
    context_tokens: int = 4096
    output_tokens: int = 1800


class OllamaFailure(RuntimeError):
    """Bounded inference failure that should activate curated fallback."""


class OllamaClient:
    """Call internal Ollama once and parse its untrusted JSON response."""

    def __init__(self, settings: OllamaSettings, transport: httpx.AsyncBaseTransport | None = None):
        self._settings = settings
        self._transport = transport

    async def generate(self, prompt: str) -> GeneratedBatch:
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
                await self._require_pinned_model(client)
                response = await client.post("/api/generate", json=request)
                response.raise_for_status()
                envelope = response.json()
                return GeneratedBatch.model_validate(json.loads(envelope["response"]))
        except (httpx.HTTPError, KeyError, TypeError, ValueError) as exc:
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
