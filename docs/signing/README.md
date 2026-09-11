# Android signing identity

Little Orbit phone and Wear OS release APKs use the same update identity. The private key is stored outside Git and must remain available for every future update.

- Subject: `CN=Little Orbit Release, OU=Open Source, O=Little Orbit, C=US`
- Key: RSA 4096-bit with SHA-256
- Validity: 2026-09-11 through 2051-09-05
- Certificate SHA-256: `43e83a420c7496ce9121339ab5bd6b01a6357161a83a95042ace56855bd89337`
- Public certificate: [`little-orbit-release-cert.pem`](little-orbit-release-cert.pem)

Verify a downloaded APK with Android SDK Build Tools:

```powershell
apksigner verify --verbose --print-certs little-orbit-1.0.0-rc.3.apk
```

The command must report that the APK verifies and that its certificate SHA-256 exactly matches this document. Also compare the APK file SHA-256 with its matching `.sha256` asset on GitHub Releases.
