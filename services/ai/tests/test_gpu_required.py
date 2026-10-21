"""Mocked CPU-only strict-GPU tests; no hardware acceptance is implied."""

import json
from dataclasses import replace
from datetime import date
from pathlib import Path
from unittest.mock import AsyncMock

import httpx
import pytest

from little_orbit_ai import gpu_inference
from little_orbit_ai.embeddings import EmbeddingSettings, OllamaEmbeddingClient
from little_orbit_ai.gpu_probe import AmdProbeIdentity, GpuRequiredFailure, GpuRequirement
from little_orbit_ai.ollama import OllamaClient, OllamaFailure, OllamaSettings
from little_orbit_ai.pipeline import select_pool


def requirement() -> GpuRequirement:
    return GpuRequirement(
        Path("unused.sock"), AmdProbeIdentity("0000:01:00.0", "0x67df", 226, 128, 0), True
    )


def transport(settings, paths, *, vram=128, digest=None, name=None):
    state = {"loaded": False}

    def handler(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        paths.append((path, json.loads(request.content) if request.content else None))
        if path == "/api/tags":
            return httpx.Response(
                200, json={"models": [{"name": settings.model, "digest": settings.manifest_digest}]}
            )
        if path == "/api/ps":
            models = [
                {
                    "name": name or settings.model,
                    "digest": digest or settings.manifest_digest,
                    "size_vram": vram,
                }
            ]
            return httpx.Response(200, json={"models": models if state["loaded"] else []})
        body = json.loads(request.content)
        if body.get("keep_alive") == 0 and "input" not in body and "prompt" not in body:
            state["loaded"] = False
            return httpx.Response(200, json={"done": True})
        state["loaded"] = True
        assert body["keep_alive"] == 30
        return _inference_response(path)

    return httpx.MockTransport(handler)


def _inference_response(path):
    if path == "/api/embed":
        return httpx.Response(200, json={"embeddings": [[0.1] * 768]})
    fixture = Path(__file__).resolve().parents[3] / "protocol/fixtures/v4/question-batch.valid.json"
    return httpx.Response(200, json={"response": fixture.read_text(encoding="utf-8")})


@pytest.mark.asyncio
@pytest.mark.parametrize("kind", ["generation", "embedding"])
async def test_both_locked_models_require_positive_offload_then_unload(monkeypatch, kind):
    proof = AsyncMock(return_value=True)
    monkeypatch.setattr(gpu_inference, "request_residency_proof", proof)
    settings = (OllamaSettings if kind == "generation" else EmbeddingSettings)(
        gpu_requirement=requirement()
    )
    paths = []
    mocked = transport(settings, paths)
    if kind == "generation":
        await OllamaClient(settings, mocked).generate("Public bounded prompt")
    else:
        result = await OllamaEmbeddingClient(settings, mocked).embed(
            ["search_document: Public concept"]
        )
        assert len(result[0]) == 768
    proof.assert_awaited_once()
    assert paths[-2] == ("/api/generate", {"model": settings.model, "keep_alive": 0})
    assert paths[-1] == ("/api/ps", None)


@pytest.mark.asyncio
@pytest.mark.parametrize("vram", [0, None, False, -1, "128"])
@pytest.mark.parametrize("kind", ["generation", "embedding"])
async def test_cpu_only_or_unknown_residency_is_fatal_not_fallback(monkeypatch, kind, vram):
    proof = AsyncMock(return_value=True)
    monkeypatch.setattr(gpu_inference, "request_residency_proof", proof)
    settings = (OllamaSettings if kind == "generation" else EmbeddingSettings)(
        gpu_requirement=requirement()
    )
    paths = []
    mocked = transport(settings, paths, vram=vram)
    with pytest.raises(GpuRequiredFailure):
        if kind == "generation":
            await OllamaClient(settings, mocked).generate("Public bounded prompt")
        else:
            await OllamaEmbeddingClient(settings, mocked).embed(["Public concept"])
    proof.assert_not_awaited()
    assert paths[-2][1]["keep_alive"] == 0


@pytest.mark.asyncio
@pytest.mark.parametrize("metadata", [{"digest": "wrong"}, {"name": "other-model"}])
async def test_resident_model_must_match_both_name_and_digest(monkeypatch, metadata):
    monkeypatch.setattr(gpu_inference, "request_residency_proof", AsyncMock(return_value=True))
    settings = OllamaSettings(gpu_requirement=requirement())
    with pytest.raises(GpuRequiredFailure):
        await OllamaClient(settings, transport(settings, [], **metadata)).generate("Public prompt")


@pytest.mark.asyncio
async def test_wrong_or_unknown_physical_device_owner_is_fatal(monkeypatch):
    monkeypatch.setattr(gpu_inference, "request_residency_proof", AsyncMock(return_value=False))
    settings = OllamaSettings(gpu_requirement=requirement())
    with pytest.raises(GpuRequiredFailure):
        await OllamaClient(settings, transport(settings, [])).generate("Public prompt")


@pytest.mark.parametrize("settings", [OllamaSettings(), EmbeddingSettings()])
def test_strict_recovery_refuses_changed_model_or_digest(settings):
    for changes in ({"model": "other"}, {"manifest_digest": "other"}):
        with pytest.raises(GpuRequiredFailure):
            replace(settings, gpu_requirement=requirement(), **changes)


def test_strict_recovery_does_not_publish_curated_fallback():
    settings = OllamaSettings(gpu_requirement=requirement())
    with pytest.raises(GpuRequiredFailure, match="curated"):
        select_pool(date(2026, 10, 21), None, [], settings, "ollama_unavailable")


@pytest.mark.asyncio
@pytest.mark.parametrize("kind", ["generation", "embedding"])
async def test_normal_amd_rejects_cpu_output_but_preserves_safe_degraded_fallback(
    monkeypatch, kind
):
    proof = AsyncMock(return_value=True)
    monkeypatch.setattr(gpu_inference, "request_residency_proof", proof)
    runtime = replace(requirement(), strict_recovery=False)
    settings = (OllamaSettings if kind == "generation" else EmbeddingSettings)(
        gpu_requirement=runtime
    )
    mocked = transport(settings, [], vram=0)
    with pytest.raises(OllamaFailure):
        if kind == "generation":
            await OllamaClient(settings, mocked).generate("Public prompt")
        else:
            await OllamaEmbeddingClient(settings, mocked).embed(["Public concept"])
    proof.assert_not_awaited()
    pool = select_pool(
        date(2026, 10, 21), None, [], OllamaSettings(gpu_requirement=runtime), "ollama_unavailable"
    )
    assert len(pool.pool.general) == 5
    assert pool.pool.fallback_reason == "ollama_unavailable"
