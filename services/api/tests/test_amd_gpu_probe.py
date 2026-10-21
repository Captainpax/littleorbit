"""CPU-only protocol tests; none of these prove real RX480 GPU acceptance."""

from __future__ import annotations

import asyncio
import copy
import json
import socket
import stat
import struct
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch

from little_orbit_ai import gpu_probe as probe


class IdleProofTests(unittest.TestCase):
    def setUp(self) -> None:
        self.identity = probe.AmdProbeIdentity("0000:01:00.0", "0x67df", 226, 128, 4_096)
        self.device: dict[str, str | int] = {
            "pci_bdf": "0000:01:00.0",
            "vendor_id": "0x1002",
            "device_id": "0x67df",
            "driver": "amdgpu",
            "render_major": 226,
            "render_minor": 128,
        }
        self.proof: dict[str, object] = {
            "schema": 1,
            "nonce": "fresh",
            "device": self.device,
            "census_complete": True,
            "owners": [],
            "errors": [],
            "samples": 2,
            "gpu_busy_percent": 0,
            "vram_used_bytes": 4_096,
            "sample_span_ms": 150,
        }

    def test_accepts_only_complete_quiet_exact_device_proof(self) -> None:
        self.assertTrue(probe.validate_idle_proof(self.proof, "fresh", self.identity))

    def test_rejects_unknown_busy_stale_and_malformed_fields(self) -> None:
        cases: dict[str, list[object]] = {
            "schema": [None, True, "1", 2],
            "nonce": [None, "previous"],
            "census_complete": [None, False, 1],
            "owners": [None, {}, [123]],
            "errors": [None, ["permission_denied"]],
            "samples": [None, True, 0, 1],
            "gpu_busy_percent": [None, True, "0", -1, 1],
            "vram_used_bytes": [None, False, "0", -1, 4_097],
            "sample_span_ms": [None, True, "1", 0, -1, 2_001],
        }
        for field, invalid_values in cases.items():
            for value in invalid_values:
                with self.subTest(field=field, value=value):
                    proof = dict(self.proof, **{field: value})
                    self.assertFalse(probe.validate_idle_proof(proof, "fresh", self.identity))

    def test_rejects_wrong_pci_driver_vendor_or_render_device(self) -> None:
        replacements: dict[str, str | int] = {
            "pci_bdf": "0000:02:00.0",
            "vendor_id": "0x10de",
            "device_id": "0x1234",
            "driver": "radeon",
            "render_major": 1,
            "render_minor": 129,
        }
        for field, value in replacements.items():
            with self.subTest(field=field):
                proof = copy.deepcopy(self.proof)
                device = dict(self.device)
                device[field] = value
                proof["device"] = device
                self.assertFalse(probe.validate_idle_proof(proof, "fresh", self.identity))

    def test_rejects_incomplete_or_nonobject_proof(self) -> None:
        malformed: tuple[object, ...] = (None, [], {}, "pass")
        for value in malformed:
            self.assertFalse(probe.validate_idle_proof(value, "fresh", self.identity))
        for key in self.proof:
            value = dict(self.proof)
            del value[key]
            self.assertFalse(probe.validate_idle_proof(value, "fresh", self.identity))

    def test_socket_requires_root_and_private_group_2000(self) -> None:
        path = Mock()
        path.lstat.return_value = SimpleNamespace(
            st_mode=stat.S_IFSOCK | 0o660, st_uid=0, st_gid=2_000, st_dev=1, st_ino=2
        )
        self.assertEqual(probe._verify_socket(path), (1, 2))
        for field, value in (
            ("st_uid", 1),
            ("st_gid", 1),
            ("st_mode", stat.S_IFSOCK | 0o666),
            ("st_mode", stat.S_IFREG | 0o660),
        ):
            with self.subTest(field=field, value=value):
                original = getattr(path.lstat.return_value, field)
                setattr(path.lstat.return_value, field, value)
                with self.assertRaises(RuntimeError):
                    probe._verify_socket(path)
                setattr(path.lstat.return_value, field, original)

    def test_peer_must_be_root(self) -> None:
        connection = Mock()
        with patch.object(socket, "SO_PEERCRED", 17, create=True):
            connection.getsockopt.return_value = struct.pack("3i", 123, 0, 2_000)
            probe._verify_root_peer(connection)
            connection.getsockopt.return_value = struct.pack("3i", 123, 65532, 2_000)
            with self.assertRaises(RuntimeError):
                probe._verify_root_peer(connection)


class ProbeTransportTests(unittest.IsolatedAsyncioTestCase):
    async def test_residency_requires_only_approved_live_gpu_owners(self) -> None:
        fixture = IdleProofTests()
        fixture.setUp()
        requirement = probe.GpuRequirement(Path("unused.sock"), fixture.identity)
        value = dict(fixture.proof, owners=[{"pid": 123, "approved": True}], vram_used_bytes=8_192)
        with patch.object(probe, "_request_proof", new=AsyncMock(return_value=(value, "fresh"))):
            self.assertTrue(await probe.request_residency_proof(requirement))
        invalid_changes: tuple[dict[str, object], ...] = (
            {"owners": []},
            {"owners": [{"pid": 123, "approved": False}]},
            {"owners": [{"pid": True, "approved": True}]},
            {"owners": [{"pid": 0, "approved": True}]},
            {"vram_used_bytes": 4_096},
            {"gpu_busy_percent": None},
            {"census_complete": False},
            {"errors": ["unknown"]},
        )
        for changes in invalid_changes:
            invalid = dict(value, **changes)
            with (
                self.subTest(changes=changes),
                patch.object(
                    probe, "_request_proof", new=AsyncMock(return_value=(invalid, "fresh"))
                ),
            ):
                self.assertFalse(await probe.request_residency_proof(requirement))

    async def test_transport_requires_fresh_nonce_and_closes_connection(self) -> None:
        identity = probe.AmdProbeIdentity("0000:01:00.0", "0x67df", 226, 128, 0)
        path = Path("probe.sock")
        reader = SimpleNamespace(readuntil=AsyncMock(return_value=b'{"nonce":"old"}\n'))
        writer = Mock()
        writer.drain = AsyncMock()
        writer.wait_closed = AsyncMock()
        with (
            patch.object(probe.os, "name", "posix"),
            patch.object(probe, "_verify_socket", return_value=(1, 2)),
            patch.object(probe, "_verify_root_peer"),
            patch.object(probe.secrets, "token_hex", return_value="new"),
            patch.object(
                asyncio,
                "open_unix_connection",
                create=True,
                new=AsyncMock(return_value=(reader, writer)),
            ),
        ):
            self.assertFalse(await probe.request_idle_proof(path, identity))
        request = json.loads(writer.write.call_args.args[0])
        self.assertEqual(request, {"schema": 1, "operation": "idle", "nonce": "new"})
        writer.close.assert_called_once()
        writer.wait_closed.assert_awaited_once()

    async def test_transport_rejects_socket_swap_before_request(self) -> None:
        path = Path("probe.sock")
        reader = Mock()
        writer = Mock()
        writer.wait_closed = AsyncMock()
        with (
            patch.object(probe.os, "name", "posix"),
            patch.object(probe, "_verify_socket", side_effect=[(1, 2), (1, 3)]),
            patch.object(probe, "_verify_root_peer"),
            patch.object(
                asyncio,
                "open_unix_connection",
                create=True,
                new=AsyncMock(return_value=(reader, writer)),
            ),
            self.assertRaisesRegex(RuntimeError, "changed"),
        ):
            await probe.request_idle_proof(path, probe.AmdProbeIdentity("pci", "device", 1, 2, 0))
        writer.write.assert_not_called()
        writer.close.assert_called_once()


if __name__ == "__main__":
    unittest.main()
