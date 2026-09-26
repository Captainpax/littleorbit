import importlib.util
import json
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest import mock

MODULE_PATH = Path(__file__).resolve().parents[1] / "release_tool.py"
SPEC = importlib.util.spec_from_file_location("release_tool", MODULE_PATH)
assert SPEC is not None and SPEC.loader is not None
TOOL = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(TOOL)


class ReleaseToolTest(unittest.TestCase):
    def _policy(self) -> dict:
        return json.loads(
            (Path(__file__).resolve().parents[1] / "policy.json").read_text(encoding="utf-8")
        )

    def _records(self) -> list[dict]:
        return [
            {
                "role": module["role"],
                "file": module["candidate_name"],
                "package": module["package"],
                "version_name": "1.3.0",
                "version_code": index,
                "bytes": index,
                "sha256": str(index) * 64,
                "signed": False,
            }
            for index, module in enumerate(self._policy()["modules"], start=1)
        ]

    def test_normalises_colon_delimited_certificate(self) -> None:
        value = ":".join(["ab"] * 32)
        self.assertEqual("ab" * 32, TOOL._normalise_digest(value))

    def test_rejects_candidate_path_traversal(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaises(TOOL.ReleaseError):
                TOOL._safe_candidate(Path(directory), "../release.apk")

    def test_rejects_embedded_qa_marker(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            apk = Path(directory) / "candidate.apk"
            with zipfile.ZipFile(apk, "w") as archive:
                archive.writestr("resources.arsc", b"Little Orbit QA")
            with self.assertRaises(TOOL.ReleaseError):
                TOOL._scan_forbidden(apk, ["Little Orbit QA"])

    def test_manifest_keeps_phone_and_wear_codes_independent(self) -> None:
        records = [
            {
                "role": "phone",
                "version_name": "1.3.0",
                "version_code": 29,
                "file": "phone.apk",
                "sha256": "1" * 64,
                "bytes": 10,
            },
            {
                "role": "wear",
                "version_name": "1.3.0",
                "version_code": 21,
                "file": "wear.apk",
                "sha256": "2" * 64,
                "bytes": 20,
            },
        ]
        manifest = TOOL._little_orbit_manifest(records, "3" * 64)
        self.assertEqual(29, manifest["PhoneVersionCode"])
        self.assertEqual(21, manifest["WearVersionCode"])

    def test_policy_pins_published_certificate(self) -> None:
        policy = self._policy()
        self.assertEqual(
            "43e83a420c7496ce9121339ab5bd6b01a6357161a83a95042ace56855bd89337",
            policy["certificate_sha256"],
        )

    def test_wear_policy_requires_watch_feature(self) -> None:
        modules = {module["role"]: module for module in self._policy()["modules"]}
        self.assertNotIn("required_feature", modules["phone"])
        self.assertEqual(
            "android.hardware.type.watch",
            modules["wear"]["required_feature"],
        )

    def test_badging_feature_parser_requires_exact_declared_feature(self) -> None:
        features = TOOL._features_from_badging(
            "  uses-feature: name='android.hardware.type.watch'\n"
            "uses-feature-not-required: name='android.hardware.location'\n"
        )
        self.assertEqual({"android.hardware.type.watch"}, features)

    def test_required_wear_feature_fails_closed(self) -> None:
        completed = mock.Mock(stdout="  uses-feature: name='android.hardware.faketouch'\n")
        with mock.patch.object(TOOL, "_tool", return_value=Path("aapt")), mock.patch.object(
            TOOL, "_run", return_value=completed
        ):
            with self.assertRaises(TOOL.ReleaseError):
                TOOL._assert_required_feature(
                    Path("wear.apk"),
                    {"role": "wear", "required_feature": "android.hardware.type.watch"},
                )

    def test_rejects_duplicate_candidate_role(self) -> None:
        records = self._records()
        records[1]["role"] = "phone"
        with self.assertRaises(TOOL.ReleaseError):
            TOOL._candidate_records({"schema": 1, "modules": records}, self._policy())

    def test_rejects_candidate_package_not_in_policy(self) -> None:
        records = self._records()
        records[0]["package"] = "com.example.impostor"
        with self.assertRaises(TOOL.ReleaseError):
            TOOL._candidate_records({"schema": 1, "modules": records}, self._policy())


if __name__ == "__main__":
    unittest.main()
