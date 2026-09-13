# RC12 verification — 2026-09-13

This record covers the RC12 shell, private activity, Markdown controls, attachment repair, isolated smoke environment, Android compatibility matrix, and signed artifacts. It records checks completed against this source tree and disposable local data.

## Automated gates

- `python -m pytest services/api/tests services/ai/tests`: 85 tests passed.
- `python -m ruff check services`: passed.
- `python -m mypy services`: 98 source files passed strict checking.
- `npm --prefix apps/web run check`, `npm --prefix apps/web run test`, and `npm --prefix apps/web run build`: ESLint, strict TypeScript, 28 Vitest tests, and the 22-page production build passed.
- `npm --prefix apps/web run test:e2e`: 16 desktop/mobile Chromium flows passed, including release fallback, patch notes/RSS, signup attestations, Wear handoff, token fragments, and admin rejection.
- Android domain, data, phone, and Wear unit tests, data/phone/Wear debug lint, and phone/Wear debug assembly passed in one 197-task Gradle run.
- `python infra/scripts/check_quality.py`: 274 source files passed the ratcheted module, function, and complexity limits.

## Attachment and API evidence

- Production PostgreSQL backup `little-orbit-20260913-075119.dump` and attachment snapshot `little-orbit-attachments-20260913-075128.files` completed before migration or container replacement. A new destructive restore drill was not performed.
- The isolated `little-orbit-smoke` Compose project started with separate PostgreSQL, attachment, and ClamAV volumes, gateway `127.0.0.1:18180`, and Mailpit `127.0.0.1:18025`. Development SMTP overrides cleared the hosted Gmail credentials and STARTTLS settings.
- Alembic reached migration `0014`. Two unique disposable `@example.com` accounts registered, received Mailpit verification, signed in, and completed confirmed pairing.
- A synthetic transparent PNG and a transparent palette GIF completed reservation, chunk upload, ClamAV scan, metadata-removing sanitizer, final quota check, and `available` state. The current couple could see their content-free attachment-ready activity event.
- Focused tests cover transparent GIF alpha handling, retry-safe activity events, active-couple authorization, monotonic seen watermarks, and Android version-floor routing for the new endpoints.
- The merged development and isolated-smoke Compose configurations both validated. The hosted stack and isolated stack reported healthy API, gateway, PostgreSQL, ClamAV, and web containers before deployment.

## Android emulator matrix

- API 29 phone: paired sign-in, Home, complete left drawer, Our Space library, Attachment smoke document, Markdown dock, and both sanitized attachment cards passed after correcting the unsupported cutout mode.
- API 30 phone: the same flow passed after the matrix exposed and corrected an API-specific theme overlay that had dropped Material inheritance.
- API 36 phone: the same flow passed. The Notes right panel opened from its toolbar control, and a sanitized PNG downloaded, passed Android's expected size/hash verification, decoded, and rendered in the attachment card.
- API 36 wide tablet: the same flow passed with the destination list visible as a static rail. Document cards remained tappable, both attachments were reachable, and the right Notes directory panel opened over the end edge.
- The Android smoke harness uses the paired account fixture and isolated loopback gateway; it never modified the connected physical Pixel or hosted accounts.
- API 34 round Wear emulator: the RC12 package installed after removing an older differently signed debug package, launched without a fatal runtime event, and displayed pairing-date unavailable, `0h 0m nearby`, and `Stale · open phone` within the round safe area.

## Signed artifacts

- Phone: version `1.0.0-rc.12`, code 16, 35,616,669 bytes, SHA-256 `0169276a6008affe9b3806315ebde269120063ac86348655312622bf8c585966`.
- Wear: version `1.0.0-rc.12`, code 15, 14,133,466 bytes, SHA-256 `9227bbb70ecf127a36a70d3f33101938df35f4b4cf62d80b71ff4a653a1c1868`.
- Both APKs passed Android v3 signature verification with certificate SHA-256 `43e83a420c7496ce9121339ab5bd6b01a6357161a83a95042ace56855bd89337`.

## Hosted release verification

- The production database was backed up before deployment, and the hosted API applied migration `0014` transactionally. API, web, gateway, PostgreSQL, ClamAV, and Ollama reported healthy after replacement; the background worker and media worker remained running. The leftover development Mailpit container was removed from the hosted Compose project.
- The public and loopback readiness routes returned HTTP 200 through the gateway. No database, API, web, worker, media, ClamAV, or Ollama host ports were added.
- RC12 was published at `2026-09-13T15:00:54.652421Z` with phone version code 16, Wear version code 15, the expected hashes, and the unchanged minimum supported phone version code 6.
- Complete-download `HEAD` checks returned 35,616,669 phone bytes and 14,133,466 Wear bytes with `Accept-Ranges: bytes`. Both first-kilobyte checks returned HTTP 206, exactly 1,024 bytes, and correct `Content-Range` totals.
- `/download`, `/patch-notes`, `/patch-notes.xml`, and `/showcase` returned HTTP 200 over the public domain; the feed used `application/rss+xml`.

## Open gates

- The full shared-edit, cursor/convergence, attachment format/quota, activity wording/unread, Smooch notification, and unpair flow on two physical phones remains open.
- The RC12 phone-to-physical-watch installer and watch upgrade flow remains open; a Wear emulator launch does not verify wireless ADB pairing.
- Battery, OEM background behavior, notification timing, destructive attachment restore, DHCP reservation, privacy/permission, and legal review gates remain open. RC12 is not the 1.0 general release.
