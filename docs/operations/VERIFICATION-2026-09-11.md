# Verification record — 2026-09-11

This record reports what was actually exercised for the 1.0 release candidate. It is evidence for review, not production approval.

## Automated checks

- Python: Ruff, strict mypy, 33 pytest tests, Alembic head `0008`, and the ratcheted size/complexity checker.
- Protocol: valid and invalid JSON fixtures consumed by Python, Java, and TypeScript; ten Vitest checks validate the browser-side contracts and release fallback.
- Web: ESLint, strict TypeScript, Vitest, Next.js production build, Docker image build, and Playwright public/admin route checks.
- Android: Java compilation, JVM update-policy/restart tests, Android lint, debug APK assembly for phone, widget, and Wear OS modules, plus two API 36 instrumentation tests covering the signed-out state and every feature activity launch.
- Gateway: eleven privacy-aware end-to-end flows through port 8180, including neutral auth responses, TOTP and recovery-code replay protection, atomic pairing, quiz reveal/report behavior, countdown concurrency, note operations, location deduplication/corrections/export boundaries, unpairing, and completed account deletion.
- Deployment shape: only gateway port 8180 is published by the base Compose stack; PostgreSQL, FastAPI, Next.js, and Ollama host ports are closed. Development Mailpit binds only to localhost.
- Data recovery: a PostgreSQL custom-format backup restored into a disposable database; privacy-safe account, couple, question, and migration counts matched before the drill database was dropped.
- Local AI: the pinned Qwen model generated seven future global pools on the RTX 4050 Laptop GPU; schema, safety, exact-hash, trigram, category, and curated-fallback gates remain in the worker path.
- Android release: phone and Wear OS `1.0.0-rc.3` APKs were built from one protected 4096-bit RSA identity and independently verified with Android `apksigner`; SHA-256 checksum sidecars were generated. The signed phone APK upgraded an RC2 API 36 emulator in place, reported version code 3, launched the cosmic home screen, and produced no runtime crash.
- Android updater: canonical release authority, package/version/size/hash/signer validation, optional-versus-required timing, process restart restoration, active-work escalation, replacement-release isolation, and API 29 lint compatibility were exercised by automated checks. A full DownloadManager-to-PackageInstaller update remains a physical-device launch gate because RC2 predates the updater.
- Public service: Nginx Proxy Manager serves valid HTTPS for `lil-orb.pax-kun.com`, the gateway firewall rule accepts only the proxy host, and Gmail SMTP delivered and consumed a real verification link in 17 seconds.
- Mobile signup regression: Android Chrome autofill populated the off-screen registration honeypot and caused a neutral rejection. The field is now hidden, read-only, and covered by desktop and mobile Playwright checks; the API records future honeypot rejections without storing submitted values.
- Download availability regression: the static web build could capture an API-unavailable fallback while containers restarted, removing the primary APK button. The fallback now contains the verified signed release URL and checksum, so the download remains available independently of API readiness.

## Launch gates still open

- Exercise permissions, background location, reminders, widgets, Data Layer delivery, tile, and complication behavior on two real phones and a Wear OS device.
- Install the signed release candidate on two real phones and a Wear OS device or emulator, then complete the full signup-to-unpair flow.
- Exercise optional deferral, interrupted download recovery, deliberately corrupt APK rejection, unknown-source permission return, installer cancellation, and successful update on a physical phone.
- Reserve `192.168.50.182` in DHCP and review the router exposure.
- Validate certificate renewal and the Nginx Proxy Manager recovery path before considering HSTS.
- Complete the public privacy/terms legal review and define production retention windows.
