"""Pinned local Ollama embeddings for semantic question de-duplication."""

from dataclasses import dataclass

import httpx

from .ollama import OllamaFailure


@dataclass(frozen=True)
class EmbeddingSettings:
    """Immutable reviewed embedding model and transport limits."""

    base_url: str = "http://ollama:11434"
    model: str = "nomic-embed-text:v1.5"
    manifest_digest: str = (
        "0a109f422b47e3a30ba2b10eca18548e944e8a23073ee3f3e947efcf3c45e59f"
    )
    dimensions: int = 768
    timeout_seconds: float = 30.0


class OllamaEmbeddingClient:
    """Embed public question concepts only after verifying the installed manifest."""

    def __init__(
        self,
        settings: EmbeddingSettings,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self.settings = settings
        self._transport = transport
        self._verified = False

    async def embed(self, texts: list[str]) -> list[list[float]]:
        """Return one finite fixed-width vector per bounded public input."""

        _validate_inputs(texts)
        timeout = httpx.Timeout(self.settings.timeout_seconds)
        try:
            async with httpx.AsyncClient(
                base_url=self.settings.base_url,
                timeout=timeout,
                transport=self._transport,
            ) as client:
                await self._require_pinned_model(client)
                response = await client.post(
                    "/api/embed",
                    json={
                        "model": self.settings.model,
                        "input": texts,
                        "truncate": False,
                        "keep_alive": 0,
                    },
                )
                response.raise_for_status()
                vectors = response.json().get("embeddings")
        except (httpx.HTTPError, TypeError, ValueError) as exc:
            raise OllamaFailure("Embedding transport failed") from exc
        return _parse_vectors(vectors, len(texts), self.settings.dimensions)

    async def _require_pinned_model(self, client: httpx.AsyncClient) -> None:
        if self._verified:
            return
        response = await client.get("/api/tags")
        response.raise_for_status()
        models = response.json().get("models", [])
        installed = next(
            (item for item in models if item.get("name") == self.settings.model),
            None,
        )
        if installed is None or installed.get("digest") != self.settings.manifest_digest:
            raise OllamaFailure("Installed embedding model does not match its pinned digest")
        self._verified = True


def _validate_inputs(texts: list[str]) -> None:
    invalid_value = any(not value or len(value) > 512 for value in texts)
    if not texts or len(texts) > 32 or invalid_value:
        raise OllamaFailure("Embedding input is outside its bounded contract")


def _parse_vectors(raw: object, count: int, dimensions: int) -> list[list[float]]:
    if not isinstance(raw, list) or len(raw) != count:
        raise OllamaFailure("Embedding response count is invalid")
    return [_parse_vector(vector, dimensions) for vector in raw]


def _parse_vector(raw: object, dimensions: int) -> list[float]:
    if not isinstance(raw, list) or len(raw) != dimensions:
        raise OllamaFailure("Embedding response width is invalid")
    values = [float(item) for item in raw]
    if any(value != value or value in (float("inf"), float("-inf")) for value in values):
        raise OllamaFailure("Embedding response contains a non-finite value")
    return values
