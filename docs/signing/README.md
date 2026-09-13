# Android signing identity

Little Orbit phone and Wear OS release APKs use the same update identity. The private key is stored outside Git and must remain available for every future update.

- Subject: `CN=Little Orbit Release, OU=Open Source, O=Little Orbit, C=US`
- Key: RSA 4096-bit with SHA-256
- Validity: 2026-09-11 through 2051-09-05
- Certificate SHA-256: `43e83a420c7496ce9121339ab5bd6b01a6357161a83a95042ace56855bd89337`
- Public certificate: [`little-orbit-release-cert.pem`](little-orbit-release-cert.pem)

Verify a downloaded APK with Android SDK Build Tools:

```powershell
apksigner verify --verbose --print-certs little-orbit-1.0.0-rc.4.apk
```

The command must report that the APK verifies and that its certificate SHA-256 exactly matches this document. Also compare the APK file SHA-256 with the value on the Little Orbit download page and its mirrored `.sha256` GitHub asset.

`infra/scripts/build-signed-android.ps1` writes `release-manifest.json` beside the two
signed APKs. It reads phone and Wear version codes from their separate Gradle metadata
files and records each byte count and SHA-256 after signature verification. Use that
manifest as the only publication input, then independently inspect both APK manifests.
Do not assume the two modules share a version code. Published metadata and bytes are
immutable, so any mismatch requires a higher corrective release.
