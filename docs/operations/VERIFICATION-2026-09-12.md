# Verification record — 2026-09-12

This record covers the RC4 first-party APK delivery change. The broader RC3 system verification remains in [`VERIFICATION-2026-09-11.md`](VERIFICATION-2026-09-11.md).

## Verified

- Release source commit `39c08a0` was tagged `v1.0.0-rc.4`; publication identity is recorded on `main` in `6e8563d`.
- Two consecutive signed builds from the release source produced identical APK hashes.
- Phone APK: 15,747,217 bytes, SHA-256 `56dd74a4640c0fd91f029c3e59c227521284d524e3bb4f6035b2a38dad88c234`.
- Wear APK: 14,121,514 bytes, SHA-256 `09e46976708a4a0279b789ce40f68efc78408cb2fe80fabccb166941b9c0fc14`.
- Both APKs passed Android `apksigner` with the pinned certificate SHA-256 `43e83a420c7496ce9121339ab5bd6b01a6357161a83a95042ace56855bd89337`.
- GitHub prerelease mirror asset sizes and API-reported SHA-256 digests match the local signed artifacts.
- The API container sees the phone APK through its read-only release mount with the exact published size and hash.
- The live metadata endpoint reports RC4, version code 4, the first-party APK URL, exact size/hash/package/signer, compatibility floor 1, and no required-update activation time.
- A complete download through `https://lil-orb.pax-kun.com` reached 100 percent and matched the source artifact byte-for-byte.
- Public `HEAD` returned `200`, content length 15,747,217, `Accept-Ranges: bytes`, the digest ETag, and checksum header.
- A public request for bytes 15,746,193 through 15,747,216 returned `206`, the exact `Content-Range`, and 1,024 bytes.
- The live download page returned `200` and contained the RC4 API URL and exact SHA-256.
- API, web, database, gateway, and Ollama health checks were healthy after deployment; the worker was running and recent application logs contained no matching runtime errors.

## Automated checks

- Python: 41 API/AI tests passed; Ruff and strict mypy passed.
- Android: domain, data, and mobile unit tests passed; mobile and Wear OS lint passed; signed release assembly passed.
- Web: ESLint, strict TypeScript, 11 Vitest tests, production build, and 12 Playwright desktop/mobile tests passed.
- Repository: Compose configuration, documentation links, source limits, and diff whitespace checks passed.

## Remaining physical-device gate

The public byte path and emulator-independent verification are complete. A physical Android device has not yet exercised an interrupted RC4 transfer, installer approval, and in-place launch. RC3 must install RC4 once from the website because RC3's updater trusted only GitHub; RC4 and later trust the versioned API endpoint.
