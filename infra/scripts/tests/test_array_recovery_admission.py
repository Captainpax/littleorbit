"""CPU-only stdlib tests; no Docker, remote-host or model-service invocation."""

from __future__ import annotations

import copy
import datetime as dt
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest import mock

SCRIPT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SCRIPT_DIR))
import array_recovery_admission as admission  # noqa: E402

NOW = dt.datetime(2026, 10, 21, 22, 0, tzinfo=dt.timezone.utc)


def seal(path: Path, payload: dict[str, object]) -> dict[str, object]:
    data = json.dumps(payload, sort_keys=True).encode()
    path.write_bytes(data)
    return {"path": str(path), "bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()}


def observation() -> dict[str, object]:
    fields = {
        "mdState": "STARTED", "mdResync": "0", "sbSyncExit": "0", "sbSyncErrs": "0",
        "mdNumMissing": "0", "mdNumWrong": "0", "mdNumNew": "0", "diskId.2": admission.DISK_ID,
    }
    for slot in (0, 1, 2):
        fields[f"rdevStatus.{slot}"] = "DISK_OK"
        fields[f"rdevNumErrors.{slot}"] = "0"
    return {
        "recordType": "little-orbit-array-observation/v1",
        "observedAt": "2026-10-21T21:59:30Z", "hostname": "na-west-2",
        "disk2Mount": {"target": "/mnt/disk2", "source": "/dev/md2p1", "fstype": "xfs",
                       "options": "rw,noatime"},
        "mdcmdStatus": "\n".join(f"{key}={value}" for key, value in fields.items()),
        "availableBytes": 500 * admission.GIB, "rootBacking": "rootfs",
        "quarantine": {"dockerEnabled": "no", "libvirtEnabled": "disable",
                       "dockerdProcesses": 0, "containerdProcesses": 0,
                       "libvirtdProcesses": 0, "cacheMounted": False},
        "runtimeImage": {"path": admission.DOCKER_IMAGE, "state": "ABSENT"},
    }


class ArrayRecoveryAdmissionTests(unittest.TestCase):
    def setUp(self) -> None:
        temporary = tempfile.TemporaryDirectory(prefix="little-orbit-admission-cpu-")
        self.addCleanup(temporary.cleanup)
        self.directory = Path(temporary.name)
        self.host = observation()
        self.source = {
            "recordType": "little-orbit-cold-size-inventory/v1", "sourceImageBytes": 2000398934016,
            "sourceImageSha256": "4827cda6514ce4548e50d9b22afee024a7441bfcd99116dcf649852a3be22e54",
            "inventorySha256": "a" * 64,
            "applicationLogicalBytes": 20 * admission.GIB, "modelLogicalBytes": 10 * admission.GIB,
        }
        self.manifest = {
            "recordType": "little-orbit-array-admission/v1",
            "target": {"hostname": "na-west-2", "disk2Serial": admission.DISK_SERIAL},
            "paths": copy.deepcopy(admission.PATHS), "services": list(admission.SERVICES),
            "restartPolicy": "no", "jobPolicy": "HOLD_UNTIL_SEPARATE_REVIEW",
            "budget": {"runtimeImageBytes": 200 * admission.GIB,
                       "applicationBytes": 20 * admission.GIB, "modelBytes": 10 * admission.GIB,
                       "stagingBytes": 10 * admission.GIB, "rollbackBytes": 30 * admission.GIB,
                       "residualBytes": 100 * admission.GIB},
        }

    def evaluate(self) -> dict[str, object]:
        self.manifest["hostObservation"] = seal(self.directory / "host.json", self.host)
        self.manifest["provenanceFiles"] = [{
            "kind": "source-inventory", "artifact": seal(self.directory / "size.json", self.source),
        }]
        return admission.admit(self.manifest, NOW)

    def test_admission_explicitly_does_not_accept_runtime(self) -> None:
        result = self.evaluate()
        self.assertEqual(result["servicesMayBeStarted"], [])
        self.assertEqual(result["runtimeActionsAvailable"], [])
        self.assertEqual(result["budget"]["requiredAvailableBytes"], 370 * admission.GIB)
        self.assertIn("fresh-on-host-recheck", result["pendingAcceptanceGates"])
        self.assertIn("database-state", result["pendingAcceptanceGates"])

    def test_budget_numeric_and_minimum_rejections(self) -> None:
        cases = (("runtimeImageBytes", 199 * admission.GIB), ("residualBytes", 99 * admission.GIB),
                 ("rollbackBytes", 29 * admission.GIB), ("applicationBytes", True),
                 ("modelBytes", 10.0), ("stagingBytes", -1))
        original = copy.deepcopy(self.manifest["budget"])
        for key, value in cases:
            with self.subTest(key=key):
                self.manifest["budget"] = {**original, key: value}
                with self.assertRaises(admission.AdmissionError):
                    self.evaluate()

    def test_capacity_includes_every_full_growth_allocation(self) -> None:
        self.host["availableBytes"] = 370 * admission.GIB - 1
        with self.assertRaisesRegex(admission.AdmissionError, "Insufficient"):
            self.evaluate()

    def test_sealed_inventory_size_is_a_budget_floor(self) -> None:
        self.manifest["budget"]["applicationBytes"] = 19 * admission.GIB
        with self.assertRaisesRegex(admission.AdmissionError, "sealed source"):
            self.evaluate()

    def test_mount_and_backing_rejections(self) -> None:
        cases = (("source", "rootfs"), ("source", "shfs"), ("source", "/dev/md1p1"),
                 ("target", "/mnt/user"), ("fstype", "fuse.shfs"), ("fstype", "btrfs"),
                 ("options", "ro,noatime"))
        original = copy.deepcopy(self.host["disk2Mount"])
        for key, value in cases:
            with self.subTest(key=key, value=value):
                self.host["disk2Mount"] = {**original, key: value}
                with self.assertRaises(admission.AdmissionError):
                    self.evaluate()

    def test_array_health_and_serial_rejections(self) -> None:
        cases = ((admission.DISK_ID, "foreign"), ("mdResync=0", "mdResync=1"),
                 ("sbSyncErrs=0", "sbSyncErrs=1"), ("rdevNumErrors.2=0", "rdevNumErrors.2=1"),
                 ("rdevStatus.2=DISK_OK", "rdevStatus.2=DISK_INVALID"))
        original = self.host["mdcmdStatus"]
        for before, after in cases:
            with self.subTest(before=before):
                self.host["mdcmdStatus"] = original.replace(before, after)
                with self.assertRaises(admission.AdmissionError):
                    self.evaluate()

    def test_observation_freshness_rejections(self) -> None:
        for value in ("2026-10-21T21:54:59Z", "2026-10-21T22:00:01Z", "2026-10-21T21:59:30"):
            with self.subTest(value=value):
                self.host["observedAt"] = value
                with self.assertRaises(admission.AdmissionError):
                    self.evaluate()

    def test_quarantine_cannot_be_relaxed_or_coerced(self) -> None:
        cases = (("dockerEnabled", "yes"), ("libvirtEnabled", "enable"), ("dockerdProcesses", 1),
                 ("containerdProcesses", False), ("libvirtdProcesses", 0.0), ("cacheMounted", 0))
        original = copy.deepcopy(self.host["quarantine"])
        for key, value in cases:
            with self.subTest(key=key):
                self.host["quarantine"] = {**original, key: value}
                with self.assertRaises(admission.AdmissionError):
                    self.evaluate()

    def test_occupied_runtime_is_not_overwritten(self) -> None:
        self.host["runtimeImage"]["state"] = "PRESENT"
        with self.assertRaisesRegex(admission.AdmissionError, "occupied"):
            self.evaluate()

    def test_service_allowlist_and_paths_are_exact(self) -> None:
        self.manifest["services"].append("scriptarr-warden")
        with self.assertRaisesRegex(admission.AdmissionError, "allowlist"):
            self.evaluate()
        self.manifest["services"] = list(admission.SERVICES)
        self.manifest["paths"]["live"] = "/mnt/cache/little-orbit-live"
        with self.assertRaisesRegex(admission.AdmissionError, "Recovery paths"):
            self.evaluate()

    def test_acceptance_booleans_and_duplicate_json_are_not_trusted(self) -> None:
        self.manifest["accepted"] = True
        with self.assertRaisesRegex(admission.AdmissionError, "fields"):
            self.evaluate()
        with self.assertRaisesRegex(admission.AdmissionError, "Duplicate"):
            admission.decode_json(b'{"accepted":false,"accepted":true}')

    def test_sealing_never_means_content_acceptance(self) -> None:
        result = self.evaluate()
        self.manifest["provenanceFiles"].append({"kind": "database-state", "artifact": seal(
            self.directory / "db.json", {"claim": "PASS"})})
        result = admission.admit(self.manifest, NOW)
        self.assertIn("database-state", result["sealedArtifactKinds"])
        self.assertIn("database-state", result["pendingAcceptanceGates"])

    def test_exact_artifact_length_hash_and_size_evidence(self) -> None:
        self.evaluate()
        descriptor = self.manifest["hostObservation"]
        descriptor["bytes"] += 1
        with self.assertRaisesRegex(admission.AdmissionError, "length"):
            admission.admit(self.manifest, NOW)
        descriptor["bytes"] -= 1
        descriptor["sha256"] = "0" * 64
        with self.assertRaisesRegex(admission.AdmissionError, "digest"):
            admission.admit(self.manifest, NOW)
        self.evaluate()
        self.manifest["provenanceFiles"] = []
        with self.assertRaisesRegex(admission.AdmissionError, "size inventory"):
            admission.admit(self.manifest, NOW)

    def test_nonexecuted_future_stage_proposals_skip_dependencies(self) -> None:
        for stage in ("database", "gpu", "private-frontend", "held-workers"):
            with self.subTest(stage=stage):
                command = admission.proposed_stage_argv(stage)
                self.assertIn("--no-deps", command)
                self.assertIn("--no-build", command)
                self.assertEqual(command[command.index("--pull") + 1], "never")
                for forbidden in ("migrate", "database-bootstrap", "attachment-init", "model-init",
                                  "scriptarr-warden"):
                    self.assertNotIn(forbidden, command)

    def test_original_cache_profile_is_unchanged(self) -> None:
        normal = (SCRIPT_DIR / "unraid-stack.sh").read_text()
        self.assertIn("require_fixed_setting LITTLE_ORBIT_DATA_ROOT /mnt/cache/little-orbit-live", normal)
        self.assertNotIn("compose.array-recovery.yaml", normal)

    def test_quiet_compose_only_calls_secret_suppressed_config(self) -> None:
        spec = importlib.util.spec_from_file_location("array_recovery_cli", SCRIPT_DIR / "array-recovery.py")
        assert spec is not None and spec.loader is not None
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        with (mock.patch.object(module.sys, "platform", "linux"),
              mock.patch.object(module.os, "geteuid", return_value=0, create=True),
              mock.patch.object(module.os, "uname", return_value=SimpleNamespace(nodename="na-west-2"), create=True),
              mock.patch.object(module, "private_environment_file"),
              mock.patch.object(module.subprocess, "run", return_value=SimpleNamespace(returncode=0)) as run):
            module.quiet_compose(["first", "second", "third"])
        args, kwargs = run.call_args
        self.assertEqual(args[0][-2:], ["config", "--quiet"])
        self.assertNotIn("up", args[0])
        self.assertNotIn("start", args[0])
        self.assertEqual(kwargs["stderr"], module.subprocess.DEVNULL)
        self.assertEqual(kwargs["stdout"], module.subprocess.DEVNULL)
        self.assertEqual(kwargs["env"], {"PATH": "/usr/bin:/bin", "LC_ALL": "C"})


if __name__ == "__main__":
    unittest.main()
