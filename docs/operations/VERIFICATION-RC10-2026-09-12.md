# RC10 verification record — 2026-09-12

This record covers pairing-based age, proximity collection, Smooches, the multi-note workspace, update discovery, and wireless-Wear pairing recovery. It does not replace the open two-phone and physical-Wear launch gate.

## Diagnostic evidence

The production couple already had mutual sharing consent and both phones had uploaded samples, so the old display was not caused by a missing account flag. Coordinate-free inspection found no qualifying nearby pair: the closest matched observation was hundreds of metres apart and later pairs were several kilometres apart. Zero nearby minutes was therefore correct for the evidence received. No threshold was widened and no time was fabricated. RC10 addresses the sparse Android collection path while retaining the two-consecutive-pair confidence rule.

The Wear review found three independent pairing risks: an older DNS-SD resolution could overwrite a newer selection, a resolved service was not firmly associated with its discovered host, and install could reuse the pre-pair port after the watch advertised its TLS connection port. RC10 sequences resolution, binds host and ports, performs bounded post-pair retries, and reads the current connect port at installation time.

## Automated checks

| Area | Command or check | Result |
|---|---|---|
| API and AI behavior | `python -m pytest -q services/api/tests services/ai/tests` | Passed, 70 tests |
| Python style and types | Ruff plus strict mypy over `services` | Passed, 84 typed source files |
| Android domain/data/widget/mobile/Wear | Unit suites plus phone, widget, and Wear lint | Passed, 163 Gradle tasks |
| Cross-language protocol | Python fixtures, Java data tests, and TypeScript fixtures | Passed; Smooch v1 and together-time v3 accepted/rejected consistently |
| Web style, types, behavior, and build | `npm --prefix apps/web run check` | Passed, 24 tests and 22 generated routes |
| Repository limits | Ratcheted line/function/complexity checker | Passed, 242 source files before final documentation sync |
| Signed Android release | `apksigner verify --verbose --print-certs` | Passed for phone and Wear with one matching signer |

Smooch unit tests cover the exact emoji vocabulary, stable phrase selection, rolling-hour boundaries, and local-week boundaries across DST; cross-language fixtures cover valid and invalid payload shape. Note hub tests cover unique-account presence and connection removal, while existing operation tests retain transform and idempotency coverage. Existing location-domain tests retain stale, accuracy, duplicate, overlap, jitter, and consent paths. Existing updater-domain tests cover optional and required policy plus restart-safe state transitions. The encrypted Smooch outbox expiry, DownloadManager stall timer, DNS-SD callback order, archived-history authorization, and full endpoint races still need instrumentation or two-device integration coverage before 1.0.

## Signed artifacts

- Phone version code 10: 23,389,918 bytes; SHA-256 `e6039a5397e1675e8d7548a6a65ede07096cc84f7a5fd82a2887a48c59220104`.
- Wear version code 10: 14,130,626 bytes; SHA-256 `22f629a96b7a513ca9162a6fcff0b7e7dfdd42558b9c1ddce0cd1c0594934f8e`.
- Certificate SHA-256: `43e83a420c7496ce9121339ab5bd6b01a6357161a83a95042ace56855bd89337`.
- Phone minimum API: 29. Wear minimum API: 30. Compatibility floor remains phone version code 6, with no RC10 enforcement time.

## Deployment and device verification

- Created `backups/postgres/little-orbit-20260912-165313.dump` before migration, deployed the rebuilt API/web/worker images, and confirmed Alembic revision `0012 (head)`. API, web, gateway, PostgreSQL, and Ollama were healthy, and only gateway port 8180 was host-bound.
- The first deployment exposed a startup race: the worker queried `notes.purge_after` while the API was still running migration 0012. Compose now makes the worker wait for API health, which occurs after Alembic finishes. The worker was restarted after the schema was at head and resumed with a successful Ollama health request and no new schema error.
- Published one immutable RC10 record at `2026-09-12T23:55:31.611659Z`. The current and history responses return version code 10, the exact phone/Wear metadata, minimum APIs 29/30, compatibility floor 6, and no enforcement time.
- Pushed release commit `207ca0e`, annotated tag `v1.0.0-rc.10`, and a GitHub prerelease recovery mirror. GitHub reports the exact 23,389,918-byte phone digest and 14,130,626-byte Wear digest plus both checksum sidecars.
- Downloaded both APKs through public HTTPS and reproduced their exact local byte counts and SHA-256 hashes. Mid-file 1,024-byte requests returned `206`, correct full-size `Content-Range`, immutable caching, ETag, byte-range support, and `X-Checksum-SHA256` through Nginx Proxy Manager.
- Confirmed `/download`, `/patch-notes`, and RSS 2.0 at `/patch-notes.xml` all present RC10. The authenticated Smooch route returns `401` before relationship lookup when called without a session.
- Upgraded the connected Pixel 8 Pro from signed RC9 to signed RC10 in place. Package inspection reports version code 10 and `1.0.0-rc.10`; account and pairing state remained available. Home rendered the Smooch spark, automatic pair age, and separated nearby estimate. More rendered Smooches, automatic update detection with a last-check instant, notification status, and the explicit nearby stop action.
- The phone had precise foreground/background location and notification permission. RC10 started `ForegroundLocationService` as an ongoing private notification with location service type. Its immediate cycle successfully posted a new authenticated location batch, increasing the owner's production sample count from seven to eight. No Android runtime error was recorded.
- The screen locked before interactive Smooch, Notes, and Wear installer views could be exercised. Their signed-build automated checks passed, but this run does not claim a completed phone-side interaction or physical-watch install.

Public checks used `https://lil-orb.pax-kun.com` through Nginx Proxy Manager and the gateway. Exact coordinates, watch addresses, pairing codes, credentials, and relationship content were not printed or retained in this record.

## Open release gate

- Exercise Smooch delivery, weekly history, notification privacy, notes conflict/archive, and proximity on two real phones.
- Install and update the companion on a physical Wear OS watch, including remembered authorization and post-pair port changes.
- Measure five-minute foreground sampling and fallback behavior across battery saver, reboot, network loss, and OEM process limits.
- Complete the full signup through unpair/archive flow, accessibility, DHCP reservation, and legal/privacy reviews.

RC10 remains a prerelease until these checks pass.
