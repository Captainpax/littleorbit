"""Strict AMD admission, worker hold and unsafe-release quarantine tests."""

import asyncio
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, Mock
from uuid import uuid4

import pytest
from little_orbit_ai.gpu_probe import GpuReleaseUnsafe
from little_orbit_ai.ollama import OllamaSettings
from pydantic import ValidationError

from little_orbit_api import ai_work_runner, gpu_coordination, worker
from little_orbit_api.ai_work_queue import WEEKLY_GENERATION, AiWorkLease
from little_orbit_api.config import Settings


def amd_settings(tmp_path, **changes):
    values = {
        "gpu_probe_backend": "amd-vulkan",
        "gpu_verify_idle_processes": True,
        "gpu_amd_pci_bdf": "0000:01:00.0",
        "gpu_amd_device_id": "0x67df",
        "gpu_amd_render_major": 226,
        "gpu_amd_render_minor": 128,
        "gpu_amd_idle_vram_bytes": 5_439_488,
        "gpu_amd_probe_socket": tmp_path / "probe.sock",
    }
    return Settings(**dict(values, **changes))


def test_amd_never_disables_guard_or_guesses_admission(tmp_path):
    with pytest.raises(ValidationError):
        Settings(gpu_probe_backend="amd-vulkan")
    for changes in ({"gpu_verify_idle_processes": False}, {"gpu_amd_idle_vram_bytes": None}):
        with pytest.raises(ValidationError):
            amd_settings(tmp_path, **changes)


@pytest.mark.asyncio
async def test_amd_idle_check_uses_host_probe_not_nvidia(monkeypatch, tmp_path):
    monkeypatch.setattr(ai_work_runner, "_wait_for_ollama_idle", AsyncMock())
    proof = AsyncMock(return_value=True)
    nvidia = AsyncMock()
    monkeypatch.setattr(ai_work_runner, "request_idle_proof", proof)
    monkeypatch.setattr(ai_work_runner, "_nvidia_smi_output", nvidia)
    assert await ai_work_runner._prepare_idle_gpu(OllamaSettings(), 5, amd_settings(tmp_path))
    proof.assert_awaited_once()
    nvidia.assert_not_awaited()


@pytest.mark.asyncio
async def test_nvidia_remains_the_default_guard(monkeypatch):
    monkeypatch.setattr(ai_work_runner, "_wait_for_ollama_idle", AsyncMock())
    nvidia = AsyncMock(side_effect=[b"", b"# gpu pid\n0 -\n"])
    monkeypatch.setattr(ai_work_runner, "_nvidia_smi_output", nvidia)
    assert await ai_work_runner._prepare_idle_gpu(OllamaSettings(), 5, Settings())
    assert nvidia.await_count == 2


@pytest.mark.asyncio
async def test_unsafe_amd_release_retains_the_exact_lock(monkeypatch, tmp_path):
    lock = Mock()
    lock.__enter__ = Mock(return_value=lock)
    lock.__exit__ = Mock(return_value=False)
    lease = AiWorkLease(uuid4(), WEEKLY_GENERATION, datetime.now(UTC), uuid4())
    for name, value in {
        "enqueue_due_weekly_work": AsyncMock(),
        "enqueue_pending_admin_work": AsyncMock(),
        "try_acquire_gpu_lock": Mock(return_value=lock),
        "_prepare_idle_gpu": AsyncMock(return_value=True),
        "claim_due_work": AsyncMock(return_value=lease),
        "_run_lease": AsyncMock(side_effect=GpuReleaseUnsafe("unknown")),
    }.items():
        monkeypatch.setattr(ai_work_runner, name, value)
    with pytest.raises(GpuReleaseUnsafe):
        await ai_work_runner.run_ai_work_cycle(
            datetime.now(UTC), amd_settings(tmp_path), OllamaSettings(), AsyncMock(), AsyncMock()
        )
    lock.quarantine.assert_called_once()


@pytest.mark.asyncio
async def test_worker_hold_starts_no_privacy_mail_or_scheduled_tasks(monkeypatch):
    monkeypatch.setattr(worker, "get_settings", lambda: Settings(worker_hold=True))
    operations = []
    for name in (
        "_poll_mail_forever",
        "_run_privacy_maintenance_forever",
        "_run_scheduled_jobs_forever",
    ):
        operation = AsyncMock()
        operations.append(operation)
        monkeypatch.setattr(worker, name, operation)
    task = asyncio.create_task(worker.run_forever())
    await asyncio.sleep(0)
    task.cancel()
    await asyncio.gather(task, return_exceptions=True)
    for operation in operations:
        operation.assert_not_awaited()


@pytest.mark.asyncio
async def test_normal_amd_coverage_keeps_fourteen_safe_dates_without_gpu_calls(
    monkeypatch, tmp_path
):
    settings = amd_settings(tmp_path)
    monkeypatch.setattr(worker, "get_settings", lambda: settings)
    monkeypatch.setattr(worker, "sync_question_reserve", AsyncMock())
    monkeypatch.setattr(worker, "curated_bank", AsyncMock(return_value=[]))
    monkeypatch.setattr(worker, "load_curated_bank", Mock(return_value=[object()]))
    monkeypatch.setattr(worker, "pool_exists", AsyncMock(return_value=False))
    monkeypatch.setattr(worker, "recent_question_prompts", AsyncMock(return_value=[]))
    monkeypatch.setattr(worker, "theme_for_date", AsyncMock(return_value=None))
    monkeypatch.setattr(worker, "select_pool", Mock(return_value=object()))
    stored = AsyncMock()
    monkeypatch.setattr(worker, "persist_pool", stored)
    await worker.ensure_question_coverage()
    assert stored.await_count == 14
    assert all(call.kwargs["allow_embeddings"] is False for call in stored.await_args_list)


@pytest.mark.asyncio
async def test_explicit_proof_phase_does_not_write_curated_success(monkeypatch, tmp_path):
    settings = amd_settings(tmp_path, gpu_recovery_proof_mode=True)
    monkeypatch.setattr(worker, "get_settings", lambda: settings)
    reserve = AsyncMock()
    stored = AsyncMock()
    monkeypatch.setattr(worker, "sync_question_reserve", reserve)
    monkeypatch.setattr(worker, "persist_pool", stored)
    await worker.ensure_question_coverage()
    reserve.assert_not_awaited()
    stored.assert_not_awaited()


@pytest.fixture
def actual_gpu_lock(tmp_path):
    path = tmp_path / "actual-gpu.lock"
    lock = gpu_coordination.try_acquire_gpu_lock(path)
    assert lock is not None
    yield lock, path
    # Test-only disposal of temporary descriptors; production has no unquarantine API.
    handle = lock._handle
    if not handle.closed:
        gpu_coordination._unlock(handle)
        handle.close()
    if handle in gpu_coordination._QUARANTINED_HANDLES:
        gpu_coordination._QUARANTINED_HANDLES.remove(handle)


def prepare_actual_lease(monkeypatch, failed):
    monkeypatch.setattr(
        ai_work_runner,
        "_execute_work",
        AsyncMock(side_effect=RuntimeError("execution failed") if failed else None),
    )

    async def heartbeat(*_args):
        await asyncio.Event().wait()

    monkeypatch.setattr(ai_work_runner, "_heartbeat_forever", heartbeat)
    monkeypatch.setattr(ai_work_runner, "complete_work", AsyncMock(return_value=True))
    return AiWorkLease(uuid4(), WEEKLY_GENERATION, datetime.now(UTC), uuid4())


@pytest.mark.asyncio
@pytest.mark.parametrize("missing_lock", [None, object()])
async def test_amd_lease_requires_actual_lock_before_creating_any_tasks(
    monkeypatch, tmp_path, missing_lock
):
    heartbeat = Mock()
    execution = Mock()
    monkeypatch.setattr(ai_work_runner, "_heartbeat_forever", heartbeat)
    monkeypatch.setattr(ai_work_runner, "_execute_work", execution)
    lease = AiWorkLease(uuid4(), WEEKLY_GENERATION, datetime.now(UTC), uuid4())
    with pytest.raises(RuntimeError, match="actual guarded GPU lock"):
        await ai_work_runner._run_lease(
            lease,
            amd_settings(tmp_path),
            OllamaSettings(),
            AsyncMock(),
            AsyncMock(),
            timedelta(hours=6),
            missing_lock,
        )
    heartbeat.assert_not_called()
    execution.assert_not_called()


@pytest.mark.asyncio
@pytest.mark.parametrize("execution_failed", [False, True])
@pytest.mark.parametrize("retry_error", [RuntimeError, asyncio.CancelledError])
async def test_actual_lease_retains_unsafe_gpu_before_database_retry_failure(
    monkeypatch, tmp_path, actual_gpu_lock, execution_failed, retry_error
):
    lock, path = actual_gpu_lock
    lease = prepare_actual_lease(monkeypatch, execution_failed)
    monkeypatch.setattr(
        ai_work_runner,
        "_wait_for_ollama_idle",
        AsyncMock(side_effect=RuntimeError("unverified cleanup")),
    )

    async def database_retry(*_args):
        assert lock._quarantined
        assert gpu_coordination.try_acquire_gpu_lock(path) is None
        raise retry_error("retry unavailable")

    monkeypatch.setattr(ai_work_runner, "retry_work", database_retry)
    with pytest.raises(retry_error), lock:
        await ai_work_runner._run_lease(
            lease,
            amd_settings(tmp_path),
            OllamaSettings(),
            AsyncMock(),
            AsyncMock(),
            timedelta(hours=6),
            lock,
        )
    assert lock._quarantined
    assert gpu_coordination.try_acquire_gpu_lock(path) is None


@pytest.mark.asyncio
@pytest.mark.parametrize("execution_failed", [False, True])
async def test_actual_lease_cancellation_during_unknown_cleanup_retains_gpu(
    monkeypatch, tmp_path, actual_gpu_lock, execution_failed
):
    lock, path = actual_gpu_lock
    lease = prepare_actual_lease(monkeypatch, execution_failed)
    cleanup_started = asyncio.Event()

    async def blocked_cleanup(*_args):
        cleanup_started.set()
        await asyncio.Event().wait()

    monkeypatch.setattr(ai_work_runner, "_wait_for_ollama_idle", blocked_cleanup)
    monkeypatch.setattr(ai_work_runner, "retry_work", AsyncMock(return_value=True))

    async def run_actual():
        with lock:
            return await ai_work_runner._run_lease(
                lease,
                amd_settings(tmp_path),
                OllamaSettings(),
                AsyncMock(),
                AsyncMock(),
                timedelta(hours=6),
                lock,
            )

    task = asyncio.create_task(run_actual())
    await asyncio.wait_for(cleanup_started.wait(), timeout=5)
    task.cancel()
    with pytest.raises(GpuReleaseUnsafe):
        await task
    assert lock._quarantined
    assert gpu_coordination.try_acquire_gpu_lock(path) is None


@pytest.mark.asyncio
async def test_verified_cleanup_allows_release_even_when_database_retry_fails(
    monkeypatch, tmp_path, actual_gpu_lock
):
    lock, path = actual_gpu_lock
    lease = prepare_actual_lease(monkeypatch, True)
    monkeypatch.setattr(ai_work_runner, "_wait_for_ollama_idle", AsyncMock())
    monkeypatch.setattr(ai_work_runner, "_amd_idle", AsyncMock(return_value=True))
    monkeypatch.setattr(
        ai_work_runner, "retry_work", AsyncMock(side_effect=RuntimeError("DB unavailable"))
    )
    with pytest.raises(RuntimeError, match="DB unavailable"), lock:
        await ai_work_runner._run_lease(
            lease,
            amd_settings(tmp_path),
            OllamaSettings(),
            AsyncMock(),
            AsyncMock(),
            timedelta(hours=6),
            lock,
        )
    assert not lock._quarantined
    acquired = gpu_coordination.try_acquire_gpu_lock(path)
    assert acquired is not None
    acquired.release()


def test_pending_verification_retains_lock_if_exception_type_was_replaced(actual_gpu_lock):
    lock, path = actual_gpu_lock
    with pytest.raises(asyncio.CancelledError), lock:
        lock.require_verified_release()
        raise asyncio.CancelledError("finalization interrupted")
    assert lock._quarantined
    assert gpu_coordination.try_acquire_gpu_lock(path) is None
