"""CPU-only serving/inert boundary and adversarial model tests."""

from copy import deepcopy
import json
from pathlib import Path
import subprocess
import tempfile
import unittest

from array_serving_test_support import OLD, contract, inert_model, model, request
import array_recovery_profile as inert
import array_serving_profile as serving


class ServingTests(unittest.TestCase):
    def valid(self, value: dict | None = None, inputs: dict | None = None) -> dict:
        return serving.validate_model(value or model(), inputs or contract(), request())

    def test_explicit_serving_delta_preserves_all_inert_guards_and_raw_input(self) -> None:
        value = model()
        original = deepcopy(value)
        result = self.valid(value)
        self.assertEqual(value, original)
        self.assertEqual(result["runtimeActionsAvailable"], [])
        self.assertEqual(result["servicesMayBeStarted"], [])
        self.assertFalse(result["runtimeAccepted"])
        self.assertNotIn("smtp.example.invalid", json.dumps(result))

    def test_preparation_stays_inert_and_cannot_be_serving(self) -> None:
        inputs = contract()
        preparation = inert_model(inputs)
        self.assertEqual(inert.validate_model(preparation, inputs["preparation"])["heldProcesses"],
                         ["worker", "media-worker"])
        with self.assertRaises(inert.ProfileError):
            self.valid(preparation)

    def test_no_extra_service_ports_privilege_build_or_model_egress(self) -> None:
        changes = [("ports", ["8180:8180"]), ("privileged", True), ("pid", "host"),
                   ("build", {"context": "."}), ("restart", "always")]
        for key, value in changes:
            candidate = model()
            candidate["services"]["gateway"][key] = value
            with self.subTest(key=key), self.assertRaises(inert.ProfileError):
                self.valid(candidate)
        candidate = model()
        candidate["services"]["ollama"]["networks"]["context-egress"] = {}
        with self.assertRaises(inert.ProfileError):
            self.valid(candidate)

    def test_credential_cutoff_tls_and_worker_start_cannot_drift(self) -> None:
        for key, value in (("WORKER_HOLD", "true"), ("SMTP_STARTTLS", "false"),
                           ("RECOVERY_MAIL_NOT_BEFORE", "2020-01-01T00:00:00+00:00")):
            candidate = model()
            candidate["services"]["worker"]["environment"][key] = value
            with self.subTest(key=key), self.assertRaises(inert.ProfileError):
                self.valid(candidate)

    def test_host_dns_source_masquerade_and_cgroup_changes_refuse(self) -> None:
        for key, value in (("dns", ["127.0.0.1"]), ("cgroup_parent", "/")):
            candidate = model()
            candidate["services"]["worker"][key] = value
            with self.subTest(key=key), self.assertRaises(inert.ProfileError):
                self.valid(candidate)
        candidate = model()
        candidate["networks"]["worker-mail-egress"]["driver_opts"][
            "com.docker.network.bridge.enable_ip_masquerade"] = "true"
        with self.assertRaises(inert.ProfileError):
            self.valid(candidate)

    def test_resource_change_bool_and_all_true_receipts_refuse(self) -> None:
        inputs = contract()
        inputs["preparation"]["resources"]["clamav"]["memoryBytes"] = 2 * 1024**3
        with self.assertRaises(inert.ProfileError):
            self.valid(inputs=inputs)
        admission = request()
        admission["gateReceipts"] = {name: True for name in serving.GATES}
        with self.assertRaises(inert.ProfileError):
            serving.validate_request(admission)
        inputs = contract()
        inputs["smtpPort"] = True
        with self.assertRaises(inert.ProfileError):
            self.valid(inputs=inputs)


@unittest.skipUnless(OLD["DOCKER"], "Local Compose config CLI unavailable; no daemon substitute")
class ComposeServingTests(unittest.TestCase):
    def test_real_four_file_config_has_exact_serving_map(self) -> None:
        inputs = contract()
        repo = Path(__file__).resolve().parents[3]
        with tempfile.TemporaryDirectory(prefix="orbit-serving-cpu-") as temporary:
            folder = Path(temporary)
            env_file = folder / "empty.env"
            env_file.write_bytes(b"")
            env = OLD["synthetic_environment"](inputs["preparation"], folder)
            env.update(ORBIT_RECOVERY_CGROUP_PARENT=inputs["cgroupParent"],
                ORBIT_RECOVERY_MAIL_CUTOVER=inputs["mailCutover"],
                ORBIT_RECOVERY_SMTP_HOST=inputs["smtpHost"], ORBIT_RECOVERY_SMTP_PORT="587",
                ORBIT_RECOVERY_DNS_IPV4=inputs["resolvers"][0])
            command = [*OLD["DOCKER"], "--project-name", "little-orbit-recovery", "--env-file",
                str(env_file), "--profile", serving.PROFILE]
            for filename in ("compose.yaml", "compose.rx480.yaml", "compose.array-recovery.yaml",
                             "compose.array-serving.yaml"):
                command.extend(["-f", str(repo / "infra" / filename)])
            command.extend(["config", "--no-env-resolution", "--no-path-resolution", "--format", "json"])
            result = subprocess.run(command, env=env, stdin=subprocess.DEVNULL,
                capture_output=True, timeout=30, check=False)
            self.assertEqual(result.returncode, 0, result.stderr.decode())
            serving.validate_model(json.loads(result.stdout), inputs, request())


if __name__ == "__main__":
    unittest.main()
