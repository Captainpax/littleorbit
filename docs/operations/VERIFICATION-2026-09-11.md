# Verification record — 2026-09-11

This record reports what was actually exercised for the 1.0 release candidate. It is evidence for review, not production approval.

## Automated checks

- Python: Ruff, strict mypy across 38 source files, 18 pytest tests, Alembic head `0007`, and the ratcheted size/complexity checker across 139 source files.
- Protocol: valid and invalid JSON fixtures consumed by Python, Java, and TypeScript; nine Vitest checks validate the browser-side contracts.
- Web: ESLint, strict TypeScript, Vitest, Next.js production build, Docker image build, and Playwright public/admin route checks.
- Android: Java compilation, JVM tests, Android lint, debug APK assembly for phone, widget, and Wear OS modules, plus two API 36 instrumentation tests covering the signed-out state and every feature activity launch.
- Gateway: eleven privacy-aware end-to-end flows through port 8180, including neutral auth responses, TOTP and recovery-code replay protection, atomic pairing, quiz reveal/report behavior, countdown concurrency, note operations, location deduplication/corrections/export boundaries, unpairing, and completed account deletion.
- Deployment shape: only gateway port 8180 is published by the base Compose stack; PostgreSQL, FastAPI, Next.js, and Ollama host ports are closed. Development Mailpit binds only to localhost.
- Data recovery: a PostgreSQL custom-format backup restored into a disposable database; privacy-safe account, couple, question, and migration counts matched before the drill database was dropped.
- Local AI: the pinned Qwen model generated seven future global pools on the RTX 4050 Laptop GPU; schema, safety, exact-hash, trigram, category, and curated-fallback gates remain in the worker path.

## Launch gates still open

- Exercise permissions, background location, reminders, widgets, Data Layer delivery, tile, and complication behavior on two real phones and a Wear OS device.
- Create and protect production Android signing material, publish the signed APK and checksum through GitHub Releases, then populate release metadata.
- Reserve `192.168.50.182`, apply and verify the Windows Firewall source restriction, and review the router exposure.
- Configure Nginx Proxy Manager only after the gateway remains healthy, validate HTTPS and recovery, then consider HSTS.
- Complete the public privacy/terms legal review and define production retention windows.
