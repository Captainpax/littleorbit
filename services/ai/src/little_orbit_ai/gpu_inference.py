"""Strict recovery-only GPU offload acceptance; CPU assistance is permitted."""

from __future__ import annotations

import asyncio
from time import monotonic

import httpx

from .gpu_probe import GpuRequiredFailure, GpuRequirement, request_residency_proof


async def post_inference(
    client: httpx.AsyncClient,
    endpoint: str,
    request: dict[str, object],
    digest: str,
    requirement: GpuRequirement | None,
) -> httpx.Response:
    """Observe this exact model's offload, then request immediate unload.

    Default operation is unchanged keep_alive=0. Strict mode holds for at most
    30 seconds solely to observe residency after this actual inference; explicit
    unload runs in finally, while the worker retains the shared host lock.
    """

    if requirement is None:
        return await client.post(endpoint, json=request)
    model = request.get("model")
    if not isinstance(model, str):
        raise GpuRequiredFailure("Strict GPU request has no pinned model")
    try:
        response = await client.post(endpoint, json=dict(request, keep_alive=30))
        response.raise_for_status()
        await _require_model_offload(client, model, digest)
        if not await request_residency_proof(requirement):
            raise GpuRequiredFailure("Physical RX480 residency is unverified")
        return response
    except (Exception, asyncio.CancelledError) as error:
        raise GpuRequiredFailure("Strict GPU inference was not accepted") from error
    finally:
        await _unload_strict_model(client, model)


async def _require_model_offload(client: httpx.AsyncClient, model: str, digest: str) -> None:
    response = await client.get("/api/ps")
    response.raise_for_status()
    payload = response.json()
    models = payload.get("models") if isinstance(payload, dict) else None
    if not isinstance(models, list) or len(models) != 1:
        raise GpuRequiredFailure("Strict GPU model residency list is incomplete")
    item = models[0]
    if not isinstance(item, dict) or item.get("name") != model or item.get("digest") != digest:
        raise GpuRequiredFailure("A different model is resident")
    used = item.get("size_vram")
    if type(used) is not int or used <= 0:
        raise GpuRequiredFailure("CPU-only inference is not accepted")


async def _unload_strict_model(client: httpx.AsyncClient, model: str) -> None:
    try:
        response = await client.post(
            "/api/generate", json={"model": model, "keep_alive": 0}, timeout=5.0
        )
        response.raise_for_status()
        deadline = monotonic() + 10
        while monotonic() < deadline:
            response = await client.get("/api/ps", timeout=5.0)
            response.raise_for_status()
            payload = response.json()
            if isinstance(payload, dict) and payload.get("models") == []:
                return
            await asyncio.sleep(0.2)
        raise GpuRequiredFailure("Strict GPU model did not unload")
    except (Exception, asyncio.CancelledError) as error:
        raise GpuRequiredFailure("Strict GPU cleanup is unverified") from error
