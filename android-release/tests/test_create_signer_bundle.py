import importlib.util
import io
import sys
import tarfile
import tempfile
import unittest
from pathlib import Path
from unittest import mock

MODULE_PATH = Path(__file__).resolve().parents[1] / "create_signer_bundle.py"
SPEC = importlib.util.spec_from_file_location("create_signer_bundle", MODULE_PATH)
assert SPEC is not None and SPEC.loader is not None
BUNDLE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(BUNDLE)


class SignerBundleTest(unittest.TestCase):
    def test_archive_contains_only_file_based_signer_inputs(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "release.p12").write_bytes(b"keystore")
            environment = root / "signing.env"
            environment.write_text(
                "ANDROID_SIGNING_STORE_FILE=release.p12\n"
                "ANDROID_SIGNING_STORE_PASSWORD=store-secret\n"
                "ANDROID_SIGNING_KEY_ALIAS=little-orbit-release\n"
                "ANDROID_SIGNING_KEY_PASSWORD=key-secret\n",
                encoding="utf-8",
            )
            values = BUNDLE._parse_environment(environment)
            with tarfile.open(fileobj=io.BytesIO(BUNDLE._archive(values, environment))) as archive:
                self.assertEqual(
                    ["release.p12", "store-password", "key-alias", "key-password"],
                    archive.getnames(),
                )
                self.assertTrue(all(member.mode == 0o600 for member in archive.getmembers()))

    def test_rejects_unknown_environment_key(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "signing.env"
            path.write_text("UNEXPECTED=value\n", encoding="utf-8")
            with self.assertRaises(BUNDLE.BundleError):
                BUNDLE._parse_environment(path)

    def test_rejects_relative_age_path(self) -> None:
        with self.assertRaises(BUNDLE.BundleError):
            BUNDLE._resolve_age("tools/age")

    def test_resolves_bare_age_name_once(self) -> None:
        with mock.patch.object(BUNDLE.shutil, "which", return_value=sys.executable):
            self.assertEqual(Path(sys.executable).resolve(), BUNDLE._resolve_age("age"))


if __name__ == "__main__":
    unittest.main()
