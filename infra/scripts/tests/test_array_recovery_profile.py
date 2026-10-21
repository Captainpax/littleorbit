"""CPU/config-only tests. Never contact a daemon, host, network or real data."""

from __future__ import annotations

import copy
import datetime as dt
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import runpy
import shutil
import subprocess
import sys
import tempfile
import unittest

REPO = Path(__file__).resolve().parents[3]
HERE = REPO / "infra/scripts"
OVERLAY = REPO / "infra/compose.array-recovery.yaml"


def compose_cli() -> list[str]:
    """Find a local CLI; tests invoke config only, never a Docker daemon."""
    explicit = os.environ.get("ORBIT_TEST_COMPOSE_BINARY")
    if explicit:
        return [explicit] if Path(explicit).is_file() else []
    standalone = shutil.which("docker-compose")
    if standalone:
        return [standalone]
    docker = shutil.which("docker")
    return [docker, "compose"] if docker else []


DOCKER = compose_cli()
SPEC = importlib.util.spec_from_file_location("candidate_array_profile", HERE / "array_recovery_profile.py")
assert SPEC and SPEC.loader
profile = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(profile)


def fixture_contract() -> dict:
    users = {name: "65532:65532" for name in profile.SERVICES}
    users.update({"web": "1001:1001", "postgres": "999:70", "ollama": "0:0", "clamav": "100:100"})
    return {
        "recordType": "little-orbit-array-profile-input/v1",
        "images": {name: "sha256:" + str(index + 1) * 64 for index, name in enumerate(profile.SERVICES)},
        "imageVolumeTargets": {name: targets for name, targets in {
            "gateway": ["/data", "/config"], "web": [], "api": [],
            "postgres": ["/var/lib/postgresql/data"], "worker": [], "context-fetcher": [],
            "ollama": ["/root/.ollama"], "media-worker": [],
            "clamav": ["/var/lib/clamav", "/var/log/clamav"],
        }.items()},
        "users": users,
        "resources": {name: {"cpus": "1.0", "memoryBytes": 256 * 1024**2, "pids": 256}
                      for name in profile.SERVICES},
        "gpu": {"pciBdf": "0000:05:00.0", "idleVramBytes": 16 * 1024**2,
                "renderGid": 18, "cardGid": 18},
    }


def synthetic_environment(contract: dict, directory: Path) -> dict[str, str]:
    env = {key: os.environ[key] for key in ("SystemRoot", "WINDIR", "PATH", "TEMP", "TMP") if key in os.environ}
    env.update({"DOCKER_CONFIG": str(directory), "COMPOSE_DISABLE_ENV_FILE": "1", "COMPOSE_ANSI": "never"})
    for path in (REPO / "infra/compose.yaml", REPO / "infra/compose.rx480.yaml", OVERLAY):
        for name in re.findall(r"\$\{([A-Z][A-Z0-9_]*)", path.read_text(encoding="utf-8")):
            env[name] = "SYNTHETIC-NOT-A-SECRET"
    for name in profile.SERVICES:
        suffix = name.upper().replace("-", "_")
        resource = contract["resources"][name]
        for prefix, value in (("IMAGE", contract["images"][name]), ("USER", contract["users"][name]),
                              ("CPUS", resource["cpus"]), ("MEMORY", resource["memoryBytes"]),
                              ("PIDS", resource["pids"])):
            env[f"ORBIT_RECOVERY_{prefix}_{suffix}"] = str(value)
    env.update({"GPU_AMD_PCI_BDF": contract["gpu"]["pciBdf"],
                "GPU_AMD_IDLE_VRAM_BYTES": str(contract["gpu"]["idleVramBytes"]),
                "ORBIT_RECOVERY_DRI_GID": "18",
                "GPU_COORDINATOR_GID": "2000", "GATEWAY_BIND_ADDRESS": "192.168.50.14",
                "GATEWAY_CADDY_IP": "10.253.14.2", "GATEWAY_API_IP": "10.253.14.3",
                "GATEWAY_INTERNAL_SUBNET": "10.253.14.0/28"})
    return env


def render_synthetic(contract: dict) -> dict:
    """Local compose config parses only; no daemon/API command is issued."""
    with tempfile.TemporaryDirectory(prefix="orbit-profile-cpu-") as temporary:
        folder = Path(temporary)
        empty_env = folder / "empty.env"
        empty_env.write_bytes(b"")
        command = [*DOCKER, "--project-name", "little-orbit-recovery",
                   "--env-file", str(empty_env), "--profile", profile.PROFILE,
                   "-f", str(REPO / "infra/compose.yaml"), "-f", str(REPO / "infra/compose.rx480.yaml"),
                   "-f", str(OVERLAY), "config",
                   "--no-env-resolution", "--no-path-resolution", "--format", "json"]
        result = subprocess.run(command, env=synthetic_environment(contract, folder),
                                stdin=subprocess.DEVNULL, capture_output=True, timeout=30, check=False)
        if result.returncode:
            raise AssertionError("Synthetic Compose config failed: " + result.stderr.decode("utf-8", "replace"))
        return json.loads(result.stdout)


class ContractTests(unittest.TestCase):
    """Always-run pure contract checks, even when Compose is unavailable."""

    def test_exact_input_contract_remains_preparation_only(self) -> None:
        contract = fixture_contract()
        self.assertEqual(profile.validate_contract(contract), contract)
        profile.validate_image_volumes(contract)

    def test_tagged_image_is_not_a_local_identity(self) -> None:
        contract = fixture_contract()
        contract["images"]["api"] = "little-orbit:latest"
        with self.assertRaises(profile.ProfileError):
            profile.validate_contract(contract)

    def test_boolean_is_not_a_resource_quantity(self) -> None:
        contract = fixture_contract()
        contract["resources"]["api"]["memoryBytes"] = True
        with self.assertRaises(profile.ProfileError):
            profile.validate_contract(contract)

    def test_owner_role_identity_cannot_replace_application_uid(self) -> None:
        contract = fixture_contract()
        contract["users"]["api"] = "0:0"
        with self.assertRaises(profile.ProfileError):
            profile.validate_contract(contract)

    def test_image_declared_unknown_volume_is_rejected(self) -> None:
        contract = fixture_contract()
        contract["imageVolumeTargets"]["api"] = ["/unreviewed-image-volume"]
        with self.assertRaises(profile.ProfileError):
            profile.validate_image_volumes(contract)

    def test_nonfinite_cpu_is_rejected_without_private_value_echo(self) -> None:
        with self.assertRaises(profile.ProfileError) as caught:
            profile.cpu("NaN")
        self.assertEqual(str(caught.exception), "CPU allocation outside bounds")


@unittest.skipUnless(DOCKER, "Local Compose CLI unavailable; do not substitute a runtime claim")
class ModelTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.contract = fixture_contract()
        cls.rendered = render_synthetic(cls.contract)
        profile.validate_model(cls.rendered, cls.contract)

    def valid(self, model: dict | None = None, contract: dict | None = None) -> dict:
        return profile.validate_model(model or self.rendered, contract or self.contract)

    def rejected(self, mutate) -> None:
        model = copy.deepcopy(self.rendered)
        mutate(model)
        with self.assertRaises(profile.ProfileError):
            self.valid(model)

    def test_real_compose_replaces_original_helpers(self) -> None:
        self.assertEqual(set(self.rendered["services"]), set(profile.SERVICES))
        self.assertFalse(self.rendered.get("volumes"))
        self.assertNotIn("model-egress", self.rendered["networks"])
        result = self.valid()
        self.assertEqual(result["servicesMayBeStarted"], [])
        self.assertEqual(result["runtimeActionsAvailable"], [])
        self.assertEqual(result["publicHostPorts"], [])

    def test_unexpected_helper_rejected(self) -> None:
        self.rejected(lambda m: m["services"].update({"migrate": copy.deepcopy(m["services"]["api"])}))

    def test_host_publication_rejected(self) -> None:
        self.rejected(lambda m: m["services"]["gateway"].update({"ports": [{"published": "8180", "target": 8180}]}))

    def test_dependency_build_and_pull_rejected(self) -> None:
        for field, value in (("depends_on", {"migrate": {"condition": "service_completed_successfully"}}),
                             ("build", {"context": "."}), ("pull_policy", "always"), ("restart", "always")):
            with self.subTest(field=field):
                self.rejected(lambda m: m["services"]["api"].update({field: value}))

    def test_cache_rootfs_fallback_rejected(self) -> None:
        self.rejected(lambda m: m["services"]["postgres"]["volumes"][0].update({"source": "/mnt/cache/little-orbit-live/postgres"}))

    def test_bind_autocreate_and_named_volume_rejected(self) -> None:
        self.rejected(lambda m: m["services"]["postgres"]["volumes"][0]["bind"].update({"create_host_path": True}))
        self.rejected(lambda m: m.update({"volumes": {"postgres-data": {}}}))

    def test_workers_use_no_application_import(self) -> None:
        for name in ("worker", "media-worker"):
            service = self.rendered["services"][name]
            self.assertEqual(service["entrypoint"], profile.HELD_ENTRYPOINT)
            self.assertEqual(service["command"], profile.HELD_COMMAND)
            self.assertEqual(service["healthcheck"], {"disable": True})
            self.rejected(lambda m: m["services"][name].update({"command": ["little_orbit_api.attachment_media"]}))

    def test_hold_and_proof_cannot_be_disabled(self) -> None:
        for key in ("WORKER_HOLD", "GPU_RECOVERY_PROOF_MODE", "GPU_VERIFY_IDLE_PROCESSES"):
            with self.subTest(key=key):
                self.rejected(lambda m: m["services"]["worker"]["environment"].update({key: "false"}))

    def test_models_are_readonly_and_have_no_egress(self) -> None:
        mount = next(item for item in self.rendered["services"]["ollama"]["volumes"] if item["target"] == "/root/.ollama")
        self.assertTrue(mount["read_only"])
        self.rejected(lambda m: m["services"]["ollama"]["networks"].update({"model-egress": None}))
        self.rejected(lambda m: m["services"]["ollama"].update({"command": ["pull", "another-model"]}))

    def test_gpu_privilege_and_wrong_device_rejected(self) -> None:
        self.rejected(lambda m: m["services"]["worker"].update({"privileged": True}))
        self.rejected(lambda m: m["services"]["worker"].update({"pid": "host"}))
        self.rejected(lambda m: m["services"]["ollama"]["devices"][0].update({"source": "/dev/dri/renderD129"}))

    def test_postgres_stock_init_rejected(self) -> None:
        self.rejected(lambda m: m["services"]["postgres"].update({"entrypoint": ["docker-entrypoint.sh"]}))

    def test_resource_and_user_drift_rejected(self) -> None:
        self.rejected(lambda m: m["services"]["api"].update({"mem_limit": 1024}))
        self.rejected(lambda m: m["services"]["api"].update({"user": "0:0"}))
        self.rejected(lambda m: m["services"]["ollama"].pop("pids_limit"))

    def test_tag_instead_of_exact_image_id_rejected(self) -> None:
        contract = copy.deepcopy(self.contract)
        contract["images"]["api"] = "little-orbit:latest"
        with self.assertRaises(profile.ProfileError):
            self.valid(contract=contract)

    def test_image_declared_uncovered_volume_rejected(self) -> None:
        contract = copy.deepcopy(self.contract)
        contract["imageVolumeTargets"]["api"] = ["/unreviewed-image-volume"]
        with self.assertRaises(profile.ProfileError):
            self.valid(contract=contract)

    def test_command_injection_and_secret_environment_rejected(self) -> None:
        self.rejected(lambda m: m["services"]["postgres"].update({"command": ["touch /cold; " + profile.POSTGRES_GUARD]}))
        self.rejected(lambda m: m["services"]["context-fetcher"].update({"environment": {"DATABASE_URL": "SYNTHETIC"}}))
        self.rejected(lambda m: m["services"]["api"].update({"entrypoint": ["sh", "-c", "alembic upgrade head"]}))
        self.rejected(lambda m: m["services"]["api"]["healthcheck"].update({"test": ["CMD-SHELL", "alembic upgrade head"]}))

    def test_unknown_extra_mount_or_socket_write_rejected(self) -> None:
        self.rejected(lambda m: m["services"]["worker"]["volumes"].append({
            "type": "bind", "source": "/var/run/docker.sock", "target": "/var/run/docker.sock"}))
        self.rejected(lambda m: next(item for item in m["services"]["worker"]["volumes"]
                                     if item["target"] == "/run/gpu-probe").update({"read_only": False}))

    def test_context_has_no_secrets_or_app_network(self) -> None:
        self.assertNotIn("environment", self.rendered["services"]["context-fetcher"])
        self.assertNotIn("env_file", self.rendered["services"]["context-fetcher"])
        self.rejected(lambda m: m["services"]["context-fetcher"].update({"env_file": [
            {"path": profile.ROOT + "/secrets/runtime.env", "required": True}]}))


@unittest.skipUnless(DOCKER, "Local Compose CLI unavailable")
class PreparationCliTests(unittest.TestCase):
    def setUp(self) -> None:
        temporary = tempfile.TemporaryDirectory(prefix="orbit-prepare-cpu-")
        self.addCleanup(temporary.cleanup)
        self.directory = Path(temporary.name)
        helper = runpy.run_path(str(REPO / "infra/scripts/tests/test_array_recovery_admission.py"))
        fixture = helper["ArrayRecoveryAdmissionTests"]()
        fixture.setUp()
        self.addCleanup(fixture.doCleanups)
        fixture.host["observedAt"] = dt.datetime.now(dt.timezone.utc).isoformat()
        fixture.manifest["hostObservation"] = helper["seal"](fixture.directory / "host.json", fixture.host)
        fixture.manifest["provenanceFiles"] = [{"kind": "source-inventory", "artifact":
                                               helper["seal"](fixture.directory / "size.json", fixture.source)}]
        self.manifest = helper["seal"](self.directory / "manifest.json", fixture.manifest)
        contract = fixture_contract()
        self.contract = helper["seal"](self.directory / "contract.json", contract)
        self.model = json.dumps(render_synthetic(contract), sort_keys=True).encode()

    def invoke(self, payload: bytes | None = None, core: Path | None = None, extra: list | None = None):
        payload = self.model if payload is None else payload
        command = [sys.executable, "-I", "-B", str(HERE / "prepare-array-recovery-profile.py"),
                   "--admission-core", str(core or REPO / "infra/scripts/array_recovery_admission.py"),
                   "--manifest", self.manifest["path"], "--manifest-sha256", self.manifest["sha256"],
                   "--contract", self.contract["path"], "--contract-sha256", self.contract["sha256"],
                   "--model-stdin-sha256", hashlib.sha256(payload).hexdigest(), *(extra or [])]
        return subprocess.run(command, input=payload, capture_output=True, check=False, timeout=30)

    def test_real_pinned_admission_and_model_preparation_never_start(self) -> None:
        result = self.invoke()
        self.assertEqual(result.returncode, 0, result.stderr)
        value = json.loads(result.stdout)
        self.assertEqual(value["stage"], "MODEL_INVARIANTS_ONLY_NOT_START_AUTHORITY")
        self.assertEqual(value["runtimeActionsAvailable"], [])
        self.assertEqual(value["servicesMayBeStarted"], [])
        self.assertEqual(value["budget"]["requiredAvailableBytes"], 370 * 1024**3)

    def test_duplicate_or_overbound_model_does_not_echo_private_input(self) -> None:
        for payload in (b'{"secret":"PRIVATE-SENTINEL","secret":2}', b"PRIVATE-SENTINEL" * 150000):
            result = self.invoke(payload)
            self.assertEqual(result.returncode, 78)
            self.assertNotIn(b"PRIVATE-SENTINEL", result.stdout + result.stderr)

    def test_changed_admission_code_is_never_executed(self) -> None:
        path = self.directory / "wrong-core.py"
        path.write_bytes(b"raise RuntimeError('PRIVATE-SENTINEL')")
        result = self.invoke(core=path)
        self.assertEqual(result.returncode, 78)
        self.assertNotIn(b"PRIVATE-SENTINEL", result.stdout + result.stderr)

    def test_no_execute_or_start_mode_exists(self) -> None:
        result = self.invoke(extra=["--execute", "--start", "postgres"])
        self.assertEqual(result.returncode, 2)
        self.assertNotIn(b"MODEL_INVARIANTS_ONLY", result.stdout)


if __name__ == "__main__":
    unittest.main()
