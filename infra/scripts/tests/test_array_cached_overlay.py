"""Synthetic code-only build checks; no original cache, daemon or private data."""

from copy import deepcopy
import io
import json
from pathlib import Path
import sys
import tarfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import array_cached_overlay as overlay


class CachedOverlayTests(unittest.TestCase):
    def setUp(self) -> None:
        self.base = {"os": "linux", "architecture": "amd64", "config": {
            "User": "65532:65532", "Env": ["PYTHON_VERSION=3.12.11", "PATH=/usr/local/bin"],
            "Cmd": ["uvicorn"], "Healthcheck": {"Test": ["NONE"]}},
            "rootfs": {"type": "layers", "diff_ids": ["sha256:" + "a" * 64]},
            "history": [{"created_by": "synthetic immutable dependencies"}]}
        self.files = {"little_orbit_api/__init__.py": b"", "little_orbit_ai/__init__.py": b"",
                      "little_orbit_api/worker.py": b"# synthetic only\n"}
        self.authority = {"sourceCommit": "b" * 40, "reviewSha256": "c" * 64,
            "dependencyInventorySha256": "d" * 64,
            "schemaAndDependencyGitDiffSha256": overlay.digest(b"")}

    def build(self) -> tuple[bytes, dict]:
        raw = overlay.canonical(self.base)
        return overlay.build_archive(raw, "sha256:" + overlay.digest(raw), self.files, self.authority)

    def test_deterministic_no_tag_no_base_payload_no_input_mutation(self) -> None:
        original = deepcopy(self.base)
        first, proof = self.build()
        self.assertEqual(self.build(), (first, proof))
        self.assertEqual(original, self.base)
        with tarfile.open(fileobj=io.BytesIO(first)) as archive:
            manifest = json.load(archive.extractfile("manifest.json"))
            self.assertEqual(manifest[0]["RepoTags"], [])
            self.assertEqual(archive.extractfile("cached/000.tar").read(), b"")
            config = json.load(archive.extractfile(manifest[0]["Config"]))
        self.assertEqual(config["rootfs"]["diff_ids"][:-1], self.base["rootfs"]["diff_ids"])
        self.assertEqual(config["config"]["Cmd"], ["python", "-m", "little_orbit_api.worker"])
        self.assertEqual(config["config"]["User"], "65532:65532")
        self.assertNotIn("Healthcheck", config["config"])
        self.assertFalse(proof["nativeAcceptance"])
        self.assertFalse(proof["newDependenciesInstalled"])

    def test_layer_contains_only_owned_readonly_code_and_provenance(self) -> None:
        data, _ = self.build()
        with tarfile.open(fileobj=io.BytesIO(data)) as outer:
            layer = outer.extractfile("recovery-layer.tar").read()
        with tarfile.open(fileobj=io.BytesIO(layer)) as archive:
            for member in archive:
                self.assertTrue(member.name.startswith("opt"))
                self.assertEqual(member.uid, 0)
                self.assertFalse(member.issym() or member.islnk())
                self.assertEqual(member.mode, 0o755 if member.isdir() else 0o644)

    def test_changed_base_hash_refused(self) -> None:
        with self.assertRaises(overlay.OverlayError):
            overlay.admit_base(overlay.canonical(self.base), "sha256:" + "f" * 64)

    def test_changed_runtime_identity_python_platform_or_entrypoint_refused(self) -> None:
        for section, name, value in (("config", "User", "0:0"),
                ("config", "Env", ["PYTHON_VERSION=3.13.0"]),
                ("config", "Entrypoint", ["bootstrap"]), ("config", "Volumes", {"/data": {}})):
            with self.subTest(name=name):
                self.setUp()
                self.base[section][name] = value
                with self.assertRaises(overlay.OverlayError):
                    self.build()
        self.setUp()
        self.base["architecture"] = "arm64"
        with self.assertRaises(overlay.OverlayError):
            self.build()

    def test_secret_traversal_install_script_and_external_source_refused(self) -> None:
        for name in (".env", "little_orbit_api/../secrets.txt", "/etc/passwd",
                     "little_orbit_api/install.sh", "other_package/__init__.py"):
            with self.subTest(name=name):
                self.setUp()
                self.files[name] = b"synthetic"
                with self.assertRaises(overlay.OverlayError):
                    self.build()

    def test_schema_or_dependency_diff_refused(self) -> None:
        self.authority["schemaAndDependencyGitDiffSha256"] = overlay.digest(b"changed")
        with self.assertRaises(overlay.OverlayError):
            self.build()

    def test_missing_package_or_extra_authority_refused(self) -> None:
        self.files.pop("little_orbit_ai/__init__.py")
        with self.assertRaises(overlay.OverlayError):
            self.build()
        self.setUp()
        self.authority["bypass"] = True
        with self.assertRaises(overlay.OverlayError):
            self.build()


if __name__ == "__main__":
    unittest.main()
