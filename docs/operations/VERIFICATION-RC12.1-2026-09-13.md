# RC12.1 verification — 2026-09-13

This record covers preview-first Our Space documents, inline private images, self-hosted partner notifications, shared motion, compatibility repairs, production migration `0015`, and the signed RC12.1 phone artifact. Checks used disposable smoke accounts unless a physical-device step is named explicitly.

## Automated gates

- Ruff passed and strict mypy passed for 106 Python source and test files.
- Pytest passed all 89 API and AI tests. The only warning is Starlette's upstream `BlockingPortal` alias deprecation.
- Android domain, data, widget, phone, and Wear unit tests; data, widget, phone, and Wear debug lint; and phone/Wear debug assembly passed in one 204-task Gradle run.
- The phone release build passed Android lint-vital and Android v3 signature verification. The unchanged RC12 Wear artifact passed v3 verification again.
- Web ESLint, strict TypeScript, 28 Vitest tests, the 22-route production build, and all 16 desktop/mobile Playwright flows passed.
- `python infra/scripts/check_quality.py` passed 292 source files under the ratcheted module, function, and complexity limits.
- Base, development, and isolated-smoke Compose configurations were checked. The smoke command uses `.env` plus the smoke override; it has no separate `.env.smoke` file.

## Notification and attachment evidence

- Migration `0015` creates account preferences, random installation registrations, short-lived notification events, and per-device delivery acknowledgements. Contract fixtures reject unknown fields, unsupported platforms, and oversized acknowledgement batches.
- The isolated notification smoke proved that a foreground socket hint contains only `notification.available`; one Smooch reached two registered installations; acknowledging one left the other pending; a new acknowledgement suppressed the legacy account-wide queue; and note-edit alert creation, 30-minute cooldown, and active-partner-view suppression behaved as specified.
- Notification tests verify no note body or attachment field can enter the event contract. Android always supplies a generic public lock-screen version and records only content-free local diagnostics.
- The isolated attachment seed uploaded a synthetic transparent PNG and animated GIF through reservation, chunk transfer, ClamAV scan, metadata-removing sanitization, and authorized availability. The note body referenced both through `attachment://` IDs.
- On API 36 the preview rendered the PNG inline after exact byte-count/hash verification. Two screenshots 11 seconds apart showed the sanitized GIF on different frames, proving on-device animation. The same inline image opened through the private verified preview path.

## Android compatibility matrix

- API 29 phone, API 30 phone, API 36 phone, and API 36 wide tablet each passed paired sign-in, Home, drawer or static rail, Our Space library, preview-first Attachment smoke document, Edit/Done editing transition, Markdown dock, and both sanitized attachment records. Both disposable partner accounts were used across the matrix.
- The API 29 gate exposed an unsupported `Matcher.replaceAll(Function)` call in Markdown privacy filtering and missing AndroidX Hilt worker code generation in the mobile module. The original run reproduced a document-open crash and WorkManager constructor failures. After replacement with API-compatible matcher iteration and adding the worker annotation processor, the full API 29 smoke passed and `PartnerNotificationWorker` completed successfully.
- An API 36 cold-emulator launch once triggered an Android not-responding dialog during heavy emulator startup. A warm rerun and the later complete matrix passed; no application exception accompanied the cold event.
- RC12.1 changes no Wear source. The signed Wear bytes, package, version code 15, hash, and certificate are identical to the RC12 artifact already launched on the round API 34 emulator. The physical watch installer was not rerun for this phone-only correction.

## Production and signed release

- PostgreSQL backup `little-orbit-20260913-094333.dump` and attachment snapshot `little-orbit-attachments-20260913-094336.files` completed before the production migration and container replacement. A new destructive restore drill was not performed.
- Production applied migration `0015` transactionally. API, web, gateway, PostgreSQL, ClamAV, and Ollama reported healthy; the worker and media worker remained running. The API ready route returned HTTP 200 and no new host port was published.
- Phone: version `1.0.0-rc.12.1`, code 17, 35,938,870 bytes, SHA-256 `df104a03b9572f186236d686b42bf170365a2806907721cb35949ac108c9060d`.
- Wear: unchanged code 15, 14,133,466 bytes, SHA-256 `9227bbb70ecf127a36a70d3f33101938df35f4b4cf62d80b71ff4a653a1c1868`.
- Both APKs use signing certificate SHA-256 `43e83a420c7496ce9121339ab5bd6b01a6357161a83a95042ace56855bd89337` and pass Android v3 verification.
- Public metadata reports phone code 17, Wear code 15, minimum phone API 29, compatibility floor 6, and no new enforcement time. Phone and Wear `HEAD` responses report the exact sizes and byte ranges; 1,024-byte requests return HTTP 206 with correct totals. Fresh complete downloads reproduce both manifest hashes.
- `/download`, `/patch-notes`, `/patch-notes.xml`, and `/showcase` return HTTP 200; RSS uses `application/rss+xml`. GitHub prerelease `v1.0.0-rc.12.1` mirrors the exact signed artifacts and tagged source.
- The signed phone APK updated the connected Pixel 8 Pro in place from code 16 to code 17 with account data preserved. The app process started its notification worker successfully and produced no fatal runtime event. The phone was locked, so this step does not claim a visual or interactive physical-phone pass.

## Open gates

- Prompt/background notification timing, Android channel overrides, generic lock-screen rendering, process kill, OEM battery limits, and independent delivery still need a two-physical-phone run.
- Two-phone simultaneous note editing, cursor convergence, inline-image behavior, attachment rejection/quota recovery, and document-edit notification suppression remain open on real devices.
- The complete physical phone/watch installer, tile, complication, and stale/offline flow was not repeated because RC12.1 reuses the unchanged RC12 Wear artifact.
- Battery, background location, destructive restore, DHCP reservation, privacy/permission, and legal review gates remain open. RC12.1 is a prerelease rather than the 1.0 general release.
