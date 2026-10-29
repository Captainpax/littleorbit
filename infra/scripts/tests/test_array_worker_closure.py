"""Synthetic offline wheel closure tests; no builds, downloads or original images."""

from copy import deepcopy
import hashlib
import io
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from zipfile import ZipFile

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import array_worker_closure as closure

BASE = "python@sha256:" + "a" * 64


def wheel(distribution: str, metadata_name: str | None = None) -> bytes:
    """Minimal synthetic ZIP, not an installable or accepted application artifact."""
    stream = io.BytesIO()
    with ZipFile(stream, "w") as archive:
        archive.writestr(f"{distribution.replace('-', '_')}-1.0.dist-info/METADATA",
            f"Metadata-Version: 2.1\nName: {metadata_name or distribution}\nVersion: 1.0\n")
    return stream.getvalue()


class ClosureTests(unittest.TestCase):
    def setUp(self) -> None:
        temporary = tempfile.TemporaryDirectory(prefix="orbit-closure-synthetic-")
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        rows = []
        for name in ("little-orbit-api", "little-orbit-ai"):
            data = wheel(name)
            filename = name.replace("-", "_") + "-1.0-py3-none-any.whl"
            (self.root / filename).write_bytes(data)
            rows.append({"distribution": name, "version": "1.0", "filename": filename,
                "bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()})
        self.manifest = {"schema": "LITTLE_ORBIT_OFFLINE_WORKER_CLOSURE_V1",
            "status": "SEALED_OFFLINE_INPUTS", "base": {"reference": BASE,
                "configSha256": "b" * 64, "metadataSha256": "c" * 64, "os": "linux",
                "architecture": "amd64", "pythonVersion": "3.12.11", "pipVersion": "1.0",
                "entrypoint": []},
            "source": {"gitCommit": "d" * 40, "treeSha256": "e" * 64,
                "reviewReceiptSha256": "f" * 64}, "wheels": rows, "originalImageMetadata": "1" * 64}

    def test_real_wheel_bytes_metadata_and_exact_hash_lock(self) -> None:
        inputs = closure.validate_manifest(self.manifest, BASE)
        result = closure.requirements(inputs, self.root)
        self.assertEqual(result.count("--hash=sha256:"), 2)
        self.assertNotIn("http", result)
        self.assertIn("little-orbit-api==1.0", result)

    def test_checked_in_pending_values_never_become_build_authority(self) -> None:
        path = Path(__file__).resolve().parents[2] / "recovery/worker-closure.pending.json"
        with self.assertRaises(closure.ClosureError):
            closure.validate_manifest(json.loads(path.read_text()), BASE)
        for key in ("base", "source", "originalImageMetadata"):
            inputs = deepcopy(self.manifest)
            inputs[key] = None
            with self.subTest(key=key), self.assertRaises(closure.ClosureError):
                closure.validate_manifest(inputs, BASE)

    def test_mutable_base_extra_wheel_duplicate_and_path_traversal_refuse(self) -> None:
        with self.assertRaises(closure.ClosureError):
            closure.validate_manifest(self.manifest, "python:3.12.11-slim-bookworm")
        inputs = deepcopy(self.manifest)
        inputs["wheels"][0]["filename"] = "../outside.whl"
        with self.assertRaises(closure.ClosureError):
            closure.requirements(inputs, self.root)
        inputs = deepcopy(self.manifest)
        inputs["wheels"].append(inputs["wheels"][0])
        with self.assertRaises(closure.ClosureError):
            closure.requirements(inputs, self.root)
        (self.root / "unsealed.whl").write_bytes(b"synthetic")
        with self.assertRaises(closure.ClosureError):
            closure.requirements(self.manifest, self.root)

    def test_base_abi_is_not_inferred_from_a_digest_string(self) -> None:
        for key, value in (("os", "windows"), ("architecture", "arm64"),
                           ("pythonVersion", "3.13.0"), ("pipVersion", None),
                           ("entrypoint", ["unreviewed-base-wrapper"])):
            inputs = deepcopy(self.manifest)
            inputs["base"][key] = value
            with self.subTest(key=key), self.assertRaises(closure.ClosureError):
                closure.validate_manifest(inputs, BASE)

    def test_hash_size_and_embedded_name_are_not_interchangeable(self) -> None:
        first = self.manifest["wheels"][0]
        data = wheel(first["distribution"], "different-package")
        (self.root / first["filename"]).write_bytes(data)
        with self.assertRaises(closure.ClosureError):
            closure.requirements(self.manifest, self.root)
        first.update(bytes=len(data), sha256=hashlib.sha256(data).hexdigest())
        with self.assertRaises(closure.ClosureError):
            closure.requirements(self.manifest, self.root)

    def test_cli_refusal_never_exports_arbitrary_json_keys_or_values(self) -> None:
        path = self.root / "manifest.json"
        path.write_bytes(b'{"PRIVATE-SENTINEL":1,"PRIVATE-SENTINEL":2}')
        result = subprocess.run([sys.executable, "-I", "-B", closure.__file__, "--manifest", str(path),
            "--wheel-root", str(self.root), "--expected-base", BASE], capture_output=True,
            timeout=10, check=False)
        self.assertEqual(result.returncode, 78)
        self.assertEqual(result.stderr.splitlines(), [b"OFFLINE_WORKER_CLOSURE_REFUSED"])
        self.assertNotIn(b"PRIVATE-SENTINEL", result.stdout + result.stderr)


if __name__ == "__main__":
    unittest.main()
