# Little Orbit 1.0 verification — 2026-09-16

This record covers the chronological together-time repair, Android live presentation, signed 1.0 artifacts, migration 0025, and production publication. It distinguishes synthetic proximity evidence from real-world physical proximity.

## Verified implementation

- The estimator evaluates the chronological union of both phone streams. Synthetic nearby-apart-nearby and unequal-cadence tests prove that an intervening observation cannot be discarded by one-to-one matching.
- Samples more than five minutes apart cannot support one decision. Counted intervals are also limited to five minutes and fractional boundaries receive no artificial one-second credit.
- A display-only live projection requires two consecutive nearby decisions and expires five minutes after the older member's newest evidence. One phone cannot create or renew it.
- Android anchors the server value to `SystemClock.elapsedRealtime()`, caps animation at the server deadline, polls every 30 seconds while visible, cancels work off-screen, and ignores stale asynchronous responses.
- Android Room schema 5 binds each encrypted queued sample to the exact relationship ID and generation. Migration 4-to-5 deletes old unscoped coordinate rows rather than guessing ownership.
- Temporary offline, throttle, or server failures retain the bounded queue. Terminal malformed or conflicting rows are isolated so they cannot block later valid samples. Permission, consent, session, or relationship loss purges private state.
- The visible service requests a fix about every two minutes; WorkManager remains a 15-minute inexact recovery path. Widgets and Wear use only authoritative observed seconds and never continue the live projection.
- Legacy v1/v2 together-time routes return a content-free `410 Gone`. The supported client uses relationship-scoped v3 batches and the v3 summary/history contract.
- Migration 0025 labels durable history provenance while retaining existing coordinate-free daily totals and corrections. Raw coordinates remain excluded from backups and expire within 24 hours.

## Automated checks

| Check | Result |
| --- | --- |
| API Ruff | Passed |
| API strict mypy | Passed, 141 source files |
| Full API pytest | Passed, 132 tests; 28 environment-gated tests skipped |
| Focused live-state/retired-route pytest | Passed, 5 tests |
| Isolated PostgreSQL together-time and retention suite | Passed, 3 tests |
| Clean Alembic upgrade through 0025 on isolated PostgreSQL | Passed |
| Web lint, strict TypeScript, Vitest, and production build | Passed; 35 tests |
| Android domain/data/mobile/widget/Wear unit tests | Passed |
| Android data/mobile/widget/Wear lint | Passed |
| Android Room migration instrumentation on API 36 | Passed, 2 tests |
| Android mobile instrumentation on API 36 | Passed, 11 tests |
| Documentation inventory and local links | Passed, 101 repository-owned Markdown files at code freeze |
| Markdown lint | Passed |
| Compose configuration resolution | Passed |

The first Android lint attempt ran concurrently with another Gradle build and collided in generated intermediates. The same complete lint command passed when rerun alone; this was a build-tool concurrency issue rather than a source finding. The first mobile instrumentation run also exposed an overbroad test that expected the protected pairing activity to remain visible while signed out. The corrected test explicitly verifies that privacy redirect and limits native-view assertions to public screens; the complete suite then passed.

## Signed artifacts

Both APKs were built from the same source tree, verified with Android `apksigner`, and signed by one RSA-4096 certificate whose SHA-256 is `43e83a420c7496ce9121339ab5bd6b01a6357161a83a95042ace56855bd89337`.

| Artifact | Version code | Bytes | SHA-256 |
| --- | ---: | ---: | --- |
| `little-orbit-1.0.0.apk` | 23 | 36,246,289 | `6a8d711eda3c662748e62cc3e0391135985ccf58123886c3f80651684ca500c0` |
| `little-orbit-wear-1.0.0.apk` | 18 | 14,189,878 | `43068ae14877ee0e158f6498a66f5987d56642521a8c4109372434e8c7fe9cd3` |

The compatibility floor is phone code 23 with enforcement scheduled for `2026-09-17T09:30:00Z`, leaving a bounded RC17 update window.

## Production evidence

Production deployment and publication evidence is appended only after migration, service health, immutable release metadata, complete and ranged downloads, patch notes/RSS, and public routing are verified.

## Open physical evidence

An API 36 phone emulator completed the Room and mobile instrumentation gates. The authorized physical Pixel appeared over wireless ADB after code freeze, but no private-account smoke or real-world proximity inspection was performed. The automated tests prove interval accounting and monotonic deadline behavior with synthetic evidence; they do not prove that two real phones were physically near each other. The two-phone measured interval, OEM battery behavior, tablet layout, and physical Wear update remain follow-up observations and must not be inferred from these results.
