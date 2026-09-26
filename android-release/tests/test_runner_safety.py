import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class RunnerSafetyTest(unittest.TestCase):
    def setUp(self) -> None:
        self.runner = (ROOT / "run-release.sh").read_text(encoding="utf-8")
        self.verifier = (ROOT / "SignerCertificateVerifier.java").read_text(encoding="utf-8")

    def test_uses_absolute_configurable_age_binary(self) -> None:
        self.assertIn(
            "ANDROID_RELEASE_AGE_BIN:-/mnt/cache/little-orbit-tools/bin/age",
            self.runner,
        )
        self.assertIn('"$AGE_BIN" --decrypt', self.runner)
        self.assertNotIn("\nage --decrypt", self.runner)

    def test_runs_images_by_content_address(self) -> None:
        self.assertIn("--iidfile", self.runner)
        self.assertIn("^sha256:[0-9a-f]{64}$", self.runner)
        self.assertIn('"$BUILDER_IMAGE"', self.runner)
        self.assertIn('"$SIGNER_IMAGE"', self.runner)
        self.assertLess(
            self.runner.index('"$BUILDER_IMAGE"'),
            self.runner.index('"$AGE_BIN" --decrypt'),
        )

    def test_bundle_verification_keeps_signer_isolation(self) -> None:
        self.assertIn("--verify-bundle", self.runner)
        self.assertIn("--network none --read-only --cap-drop ALL", self.runner)
        self.assertIn("container-verify-signer.sh", self.runner)
        self.assertIn("store.getKey(alias, keyPassword)", self.verifier)
        self.assertIn("key instanceof PrivateKey", self.verifier)
        self.assertIn('MessageDigest.getInstance("SHA-256")', self.verifier)

    def test_disposable_source_has_a_dedicated_one_level_root(self) -> None:
        self.assertIn("/mnt/cache/little-orbit-deploy/repo) ;;", self.runner)
        self.assertNotIn("/mnt/cache/little-orbit-deploy/*) ;;", self.runner)
        self.assertIn(
            "/mnt/cache/little-orbit-deploy/android-signing-drills/little-orbit-*",
            self.runner,
        )
        self.assertIn('test "$(dirname "$SOURCE")" =', self.runner)

    def test_windows_build_and_publish_recheck_wear_feature(self) -> None:
        repository = ROOT.parent
        for name in ("build-signed-android.ps1", "publish-signed-android.ps1"):
            script = (repository / "infra" / "scripts" / name).read_text(encoding="utf-8")
            self.assertIn("function Assert-WearFeature", script)
            self.assertIn("android\\.hardware\\.type\\.watch", script)
            self.assertIn("Assert-WearFeature $aapt $wearSource", script)


if __name__ == "__main__":
    unittest.main()
