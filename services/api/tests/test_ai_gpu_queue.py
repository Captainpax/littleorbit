"""Shared-GPU queue ordering, safe coverage, and host-boundary tests."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path
from unittest.mock import AsyncMock, Mock
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from little_orbit_ai.ollama import OllamaSettings

from little_orbit_api import ai_work_runner, worker
from little_orbit_api.ai_work_queue import WEEKLY_GENERATION, AiWorkLease
from little_orbit_api.config import Settings
from little_orbit_api.gpu_coordination import try_acquire_gpu_lock
from little_orbit_api.main import create_app


class _FakeGpuLock:
    def __init__(self, state: list[bool], trace: list[str]) -> None:
        self._state = state
        self._trace = trace

    def __enter__(self) -> _FakeGpuLock:
        self._state[0] = True
        self._trace.append("file_lock")
        return self

    def __exit__(self, *_args: object) -> None:
        self._state[0] = False


async def test_weekday_coverage_seeds_fourteen_days_without_embeddings(
    monkeypatch,
) -> None:
    stored = AsyncMock()
    monkeypatch.setattr(worker, "sync_question_reserve", AsyncMock())
    monkeypatch.setattr(worker, "curated_bank", AsyncMock(return_value=[]))
    monkeypatch.setattr(worker, "load_curated_bank", Mock(return_value=[object()]))
    monkeypatch.setattr(worker, "pool_exists", AsyncMock(return_value=False))
    monkeypatch.setattr(worker, "replace_unanswered_pool", AsyncMock(return_value=True))
    monkeypatch.setattr(worker, "recent_question_prompts", AsyncMock(return_value=[]))
    monkeypatch.setattr(worker, "theme_for_date", AsyncMock(return_value=None))
    monkeypatch.setattr(worker, "select_pool", Mock(return_value=object()))
    monkeypatch.setattr(worker, "persist_pool", stored)
    monkeypatch.setattr(worker, "get_settings", lambda: Settings(ai_coverage_days=14))

    await worker.ensure_question_coverage()

    assert stored.await_count == 14
    assert all(call.kwargs["allow_embeddings"] is False for call in stored.await_args_list)


async def test_gpu_file_lock_precedes_queue_and_ai_run_claim(
    monkeypatch, tmp_path: Path
) -> None:
    active = [False]
    trace: list[str] = []
    lease = AiWorkLease(
        id=uuid4(),
        kind=WEEKLY_GENERATION,
        scheduled_at=datetime(2026, 9, 27, 10, tzinfo=UTC),
        token=uuid4(),
    )

    async def claim(*_args, **_kwargs):
        assert active[0]
        trace.append("queue_claim")
        return lease

    async def claim_run(*_args, **_kwargs):
        assert active[0]
        trace.append("ai_run_claim")
        return True

    async def generate(_week, *, force=False):
        assert active[0] and force is False
        return {
            "generated_days": 7,
            "fallback_days": 0,
            "existing_days": 0,
            "context_stale_sources": 0,
        }

    patches = {
        "enqueue_due_weekly_work": AsyncMock(),
        "enqueue_pending_admin_work": AsyncMock(),
        "try_acquire_gpu_lock": Mock(return_value=_FakeGpuLock(active, trace)),
        "claim_due_work": claim,
        "lease_is_current": AsyncMock(return_value=True),
        "claim_ai_run": claim_run,
        "finish_ai_run": AsyncMock(),
        "heartbeat_work": AsyncMock(return_value=True),
        "complete_work": AsyncMock(return_value=True),
        "_wait_for_ollama_idle": AsyncMock(),
    }
    for name, value in patches.items():
        monkeypatch.setattr(ai_work_runner, name, value)

    settings = Settings(gpu_lock_path=tmp_path / "gpu.lock")
    outcome = await ai_work_runner.run_ai_work_cycle(
        datetime(2026, 9, 27, 10, tzinfo=UTC),
        settings,
        OllamaSettings(),
        generate,
        AsyncMock(),
    )

    assert outcome == "passed"
    assert trace == ["file_lock", "queue_claim", "ai_run_claim"]
    assert not active[0]


async def test_stale_gpu_process_defers_before_queue_claim(
    monkeypatch, tmp_path: Path
) -> None:
    claim = AsyncMock()
    deferred = AsyncMock(return_value=True)
    monkeypatch.setattr(ai_work_runner, "enqueue_due_weekly_work", AsyncMock())
    monkeypatch.setattr(ai_work_runner, "enqueue_pending_admin_work", AsyncMock())
    monkeypatch.setattr(
        ai_work_runner,
        "try_acquire_gpu_lock",
        lambda path: try_acquire_gpu_lock(path),
    )
    monkeypatch.setattr(ai_work_runner, "_prepare_idle_gpu", AsyncMock(return_value=False))
    monkeypatch.setattr(ai_work_runner, "defer_due_work", deferred)
    monkeypatch.setattr(ai_work_runner, "claim_due_work", claim)

    settings = Settings(
        gpu_lock_path=tmp_path / "gpu.lock",
        gpu_verify_idle_processes=True,
    )
    outcome = await ai_work_runner.run_ai_work_cycle(
        datetime(2026, 9, 27, 10, tzinfo=UTC),
        settings,
        OllamaSettings(),
        AsyncMock(),
        AsyncMock(),
    )

    assert outcome == "gpu_process_busy"
    deferred.assert_awaited_once()
    claim.assert_not_awaited()


async def test_failed_unload_uses_one_bounded_cleanup_window(monkeypatch) -> None:
    lease = AiWorkLease(
        id=uuid4(),
        kind=WEEKLY_GENERATION,
        scheduled_at=datetime(2026, 9, 27, 10, tzinfo=UTC),
        token=uuid4(),
    )
    unload = AsyncMock(side_effect=RuntimeError("still loaded"))
    monkeypatch.setattr(ai_work_runner, "_execute_work", AsyncMock())
    monkeypatch.setattr(ai_work_runner, "_wait_for_ollama_idle", unload)
    monkeypatch.setattr(ai_work_runner, "retry_work", AsyncMock(return_value=True))

    with pytest.raises(RuntimeError, match="still loaded"):
        await ai_work_runner._run_lease(
            lease,
            Settings(),
            OllamaSettings(),
            AsyncMock(),
            AsyncMock(),
            timedelta(hours=6),
        )

    assert unload.await_count == 1


async def test_fresh_legacy_ai_run_retries_instead_of_completing_queue(
    monkeypatch,
) -> None:
    monkeypatch.setattr(ai_work_runner, "claim_ai_run", AsyncMock(return_value=False))
    monkeypatch.setattr(
        ai_work_runner, "ai_run_is_finished", AsyncMock(return_value=False)
    )
    generate = AsyncMock()
    lease = AiWorkLease(
        id=uuid4(),
        kind=WEEKLY_GENERATION,
        scheduled_at=datetime(2026, 9, 27, 10, tzinfo=UTC),
        token=uuid4(),
    )

    with pytest.raises(RuntimeError, match="already active"):
        await ai_work_runner._run_generation_horizon(
            lease, datetime(2026, 9, 28, tzinfo=UTC).date(), generate
        )

    generate.assert_not_awaited()


def test_gpu_lock_keeps_one_stable_exclusive_inode(tmp_path: Path) -> None:
    path = tmp_path / "shared" / "gpu.lock"
    first = try_acquire_gpu_lock(path)
    assert first is not None
    assert try_acquire_gpu_lock(path) is None
    inode = path.stat().st_ino
    first.release()
    second = try_acquire_gpu_lock(path)
    assert second is not None
    assert path.stat().st_ino == inode
    second.release()


def test_gpu_lock_rejects_a_hardlinked_inode(tmp_path: Path) -> None:
    path = tmp_path / "gpu.lock"
    path.touch()
    (tmp_path / "gpu-alias.lock").hardlink_to(path)

    with pytest.raises(RuntimeError, match="exactly one link"):
        try_acquire_gpu_lock(path)


def test_gpu_lock_rejects_a_symbolic_link(tmp_path: Path) -> None:
    target = tmp_path / "target.lock"
    target.touch()
    path = tmp_path / "gpu.lock"
    try:
        path.symlink_to(target)
    except OSError:
        pytest.skip("symbolic links are unavailable on this test host")

    with pytest.raises((OSError, RuntimeError)):
        try_acquire_gpu_lock(path)


def test_gpu_runtime_is_always_below_the_stale_lease_window() -> None:
    settings = Settings(
        ai_work_max_runtime_seconds=7_000,
        ai_lease_stale_minutes=30,
        ai_lease_heartbeat_seconds=15,
        gpu_release_timeout_seconds=600,
    )

    runtime = ai_work_runner._runtime_limit_seconds(settings)
    assert runtime == 1_140
    assert runtime + settings.gpu_release_timeout_seconds < 30 * 60


@pytest.mark.parametrize(
    ("output", "active"),
    [
        (b"# gpu pid type sm mem enc dec command\n0 - - - - - - -\n", False),
        (b"# gpu pid type sm mem enc dec command\n0 4242 G 0 0 64 0 ffmpeg\n", True),
        (b"0 5252 C 80 20 0 0 ollama_llama_server\n", True),
    ],
)
def test_gpu_process_monitor_detects_encoder_and_compute_pids(
    output: bytes, active: bool
) -> None:
    assert ai_work_runner._pmon_has_active_pid(output) is active


def test_trusted_host_comes_from_public_base_url_not_old_lan_address() -> None:
    app = create_app(Settings(public_base_url="https://orbit.example.test"))
    with TestClient(app) as client:
        allowed = client.get("/openapi.json", headers={"host": "orbit.example.test"})
        old_host = client.get("/openapi.json", headers={"host": "192.168.50.182"})
        new_host = client.get("/openapi.json", headers={"host": "192.168.50.14"})

    assert allowed.status_code == 200
    assert old_host.status_code == 400
    assert new_host.status_code == 400
