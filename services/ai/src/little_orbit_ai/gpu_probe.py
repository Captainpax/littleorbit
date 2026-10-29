"""Fresh, bounded AMD ownership proof from a separately admitted host probe.

The worker never receives host PID access, a Docker socket, or privileged mode.
Only the root-owned host service can attest a complete DRM descriptor census.
Missing credentials, identity, metrics, or census visibility is not idle.
"""

from __future__ import annotations

import asyncio
import json
import os
import secrets
import socket
import stat
import struct
from dataclasses import dataclass
from pathlib import Path
from typing import Any

MAX_PROBE_BYTES = 8_192
PROBE_TIMEOUT_SECONDS = 5
PROBE_SCHEMA = 2


class GpuReleaseUnsafe(RuntimeError):
    """GPU ownership is unknown after unload; do not release the shared lock."""


@dataclass(frozen=True)
class AmdProbeIdentity:
    """Exact device and quiet VRAM ceiling from a reviewed host admission."""

    pci_bdf: str
    device_id: str
    render_major: int
    render_minor: int
    idle_vram_bytes: int


@dataclass(frozen=True)
class GpuRequirement:
    """Strict recovery mode, bound to an admitted physical RX480 and host probe."""

    socket_path: Path
    identity: AmdProbeIdentity
    strict_recovery: bool = False


class GpuRequiredFailure(RuntimeError):
    """Strict recovery must stop; this is deliberately not a fallback exception."""


def validate_idle_proof(value: object, nonce: str, identity: AmdProbeIdentity) -> bool:
    """Reject partial, stale, malformed, wrong-device and busy attestations."""

    if not isinstance(value, dict) or not _valid_observation(value, nonce, identity):
        return False
    if value.get("owners") != [] or value["vram_used_bytes"] > identity.idle_vram_bytes:
        return False
    # A suspended device may return EBUSY for its sensor. Preserve that missing
    # reading as null; a fresh, previously active runtime-PM state proves quiet
    # hardware separately. Never turn an unavailable sensor into a zero value.
    return value["gpu_busy_percent"] in (None, 0)


def _valid_observation(value: dict[str, Any], nonce: str, identity: AmdProbeIdentity) -> bool:
    return bool(
        _matches_device(value, nonce, identity)
        and value.get("census_complete") is True
        and value.get("errors") == []
        and _valid_metrics(value)
    )


def _matches_device(value: dict[str, Any], nonce: str, identity: AmdProbeIdentity) -> bool:
    if value.get("nonce") != nonce:
        return False
    if type(value.get("schema")) is not int or value["schema"] != PROBE_SCHEMA:
        return False
    expected_device = {
        "pci_bdf": identity.pci_bdf,
        "vendor_id": "0x1002",
        "device_id": identity.device_id,
        "driver": "amdgpu",
        "render_major": identity.render_major,
        "render_minor": identity.render_minor,
    }
    return bool(value.get("device") == expected_device)


def _valid_metrics(value: dict[str, Any]) -> bool:
    if type(value.get("samples")) is not int or value["samples"] < 2:
        return False
    for name in ("vram_used_bytes", "sample_span_ms", "runtime_active_ms"):
        if type(value.get(name)) is not int or value[name] < 0:
            return False
    if not 0 < value["sample_span_ms"] <= 2_000:
        return False
    return _valid_busy_observation(value)


def _valid_busy_observation(value: dict[str, Any]) -> bool:
    if not {"gpu_busy_percent", "gpu_busy_errno"}.issubset(value):
        return False
    power = value.get("runtime_status")
    if power not in ("active", "suspended"):
        return False
    if power == "suspended" and value["runtime_active_ms"] == 0:
        return False
    busy = value["gpu_busy_percent"]
    if type(busy) is int:
        return bool(0 <= busy <= 100 and value["gpu_busy_errno"] is None)
    return bool(
        busy is None and value["gpu_busy_errno"] == "EBUSY"
        and power == "suspended" and value["runtime_active_ms"] > 0
    )


def _verify_socket(path: Path) -> tuple[int, int]:
    info = path.lstat()
    if not stat.S_ISSOCK(info.st_mode) or info.st_uid != 0:
        raise RuntimeError("AMD ownership probe must be a root-owned socket")
    if info.st_mode & 0o007 or info.st_gid != 2_000:
        raise RuntimeError("AMD probe socket must be private to coordinator GID 2000")
    return info.st_dev, info.st_ino


def _verify_root_peer(connection: Any) -> None:
    if not hasattr(socket, "SO_PEERCRED"):
        raise RuntimeError("AMD probe requires Linux peer credentials")
    credentials = connection.getsockopt(socket.SOL_SOCKET, socket.SO_PEERCRED, 12)
    _pid, uid, _gid = struct.unpack("3i", credentials)
    if uid != 0:
        raise RuntimeError("AMD probe peer is not host root")


async def request_idle_proof(path: Path, identity: AmdProbeIdentity) -> bool:
    """Use a one-use nonce and Linux peer credentials; never trust a saved PASS."""

    value, nonce = await _request_proof(path, "idle")
    return validate_idle_proof(value, nonce, identity)


async def request_residency_proof(requirement: GpuRequirement) -> bool:
    """Require only the admitted Ollama container to own this physical device."""

    value, nonce = await _request_proof(requirement.socket_path, "residency")
    if not isinstance(value, dict) or not _valid_observation(value, nonce, requirement.identity):
        return False
    if not _approved_owners(value.get("owners")):
        return False
    busy = value.get("gpu_busy_percent")
    if value["runtime_status"] != "active" or type(busy) is not int:
        return False
    used = value.get("vram_used_bytes")
    return type(used) is int and used > requirement.identity.idle_vram_bytes


def _approved_owners(value: object) -> bool:
    if not isinstance(value, list) or not value:
        return False
    for owner in value:
        if not isinstance(owner, dict) or owner.get("approved") is not True:
            return False
        if type(owner.get("pid")) is not int or owner["pid"] <= 0:
            return False
    return True


async def _request_proof(path: Path, operation: str) -> tuple[object, str]:
    if os.name != "posix":
        raise RuntimeError("AMD ownership proof requires a Linux host probe")
    nonce = secrets.token_hex(32)
    async with asyncio.timeout(PROBE_TIMEOUT_SECONDS):
        before = _verify_socket(path)
        open_connection = getattr(asyncio, "open_unix_connection", None)
        if open_connection is None:
            raise RuntimeError("AMD probe requires Unix socket support")
        reader, writer = await open_connection(path, limit=MAX_PROBE_BYTES)
        try:
            _verify_root_peer(writer.get_extra_info("socket"))
            if before != _verify_socket(path):
                raise RuntimeError("AMD probe socket changed during connection")
            request = {"schema": PROBE_SCHEMA, "operation": operation, "nonce": nonce}
            writer.write(json.dumps(request).encode("ascii") + b"\n")
            await writer.drain()
            try:
                raw = await reader.readuntil(b"\n")
            except (asyncio.IncompleteReadError, asyncio.LimitOverrunError) as error:
                raise RuntimeError("AMD ownership proof is incomplete or oversized") from error
            if len(raw) > MAX_PROBE_BYTES:
                raise RuntimeError("AMD ownership proof exceeded its byte limit")
            return json.loads(raw), nonce
        finally:
            writer.close()
            await writer.wait_closed()
