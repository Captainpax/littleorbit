# 1.2.0 release and rollout verification — 2026-09-21

This record follows the initial 1.2.0 implementation report dated 2026-09-20. It
records the replacement signed Android candidate, disposable-stack checks, and
the production rollout. Times in this record are UTC. Checks that were waived,
unavailable, or still pending are called out rather than treated as passed.

## Automated and database evidence

- A disposable PostgreSQL 17 database using the pinned pgvector image applied
  migrations `0001` through `0029`, downgraded `0029` through `0026`, and then
  reapplied `0027` through `0029` successfully.
- The complete API and AI suite passed with 217 tests. A separate non-database
  run passed 182 tests with 35 database-dependent skips.
- Ruff passed. Mypy passed all 186 checked source files. The ratcheted source
  quality check passed all 474 files.
- The web check passed lint, strict type checking, 36 tests, and the production
  Next.js build. Its generated route inventory contained no `/admin` route.
- Android phone, data, domain, and Wear unit tests plus debug, smoke, and release
  lint/build tasks passed. The API 36 tablet completed the connected smoke suite
  after the Wear-artifact source split, and release Wear-artifact isolation
  passed.
- Big Orbit unit tests, smoke assembly, smoke lint, release lint, release build,
  signature inspection, and fixed-endpoint policy checks passed.

## Immutable release identities

The first signed phone candidate used version code 27. Independent APK
inspection found the QA-only name `little-orbit-wear-smoke.apk` retained in
production bytecode. It was never staged or published. Code 27 and its bytes are
permanently discarded.

The Little Orbit release identity is:

- Phone `1.2.0` code 28, 37,695,087 bytes, SHA-256
  `aaa8c98d452db6d87c687f25cd2630432b64481ab6753c2bdb7bdb5baa7dc04f`.
  Two signed pre-tag preparation builds were superseded after confirming that Android embeds
  source-control provenance; neither was staged or published.
- Wear `1.1.1` code 20, 14,737,940 bytes, SHA-256
  `b5f2af70402b6c8c5ff6feae91b5f23a32bd7c0ccea91b032ab705f8013d7f2b`.
  These are the unchanged, byte-identical 1.1.1 Wear bytes.
- Both APKs use signing-certificate SHA-256
  `43e83a420c7496ce9121339ab5bd6b01a6357161a83a95042ace56855bd89337`.
- The compatibility floor remains phone code 23 and no forced-update deadline
  is configured.

The release scanner found no fixed smoke endpoint, QA label, smoke package,
smoke-APK entry, or smoke signing metadata in the code-28 phone artifact. The
bare loopback string that remains in an AndroidX ConstraintLayout diagnostic
helper is not a Little Orbit endpoint.

The first minified Big Orbit candidate, code 1, crashed before its first activity because R8
removed the reflectively created WorkManager Room database constructor. It was never published,
its bytes are discarded, and the release-mode cold-launch check is now part of the build script.

The published Big Orbit release is package `com.littleorbit.bigorbit`, version `1.0.0`
code 2, 2,475,090 bytes, SHA-256
`ef4c10509709504394078835d1b74db44788999fff65dfb0f68e8bee7821a824`, and
signing-certificate SHA-256
`04dc3502933faaa99dfd6641acc52b2bd71c9895087cb3060e3ce92dd8406f8c`.
Its signer is independent from Little Orbit. Inspection found no QA endpoint,
label, package, signing metadata, or bundled APK.

## Disposable-stack and device evidence

- The isolated smoke API, worker, PostgreSQL, Mailpit, and gateway were healthy.
- Shared partner names were set from each disposable account and rendered as
  `Moon Owl` and `Starlight` on the physical Pixel and API 36 tablet. A
  contact-shaped email value was rejected.
- Big Orbit smoke enrolled on the tablet, received notification permission, and
  opened every console destination without a crash. Two activity crashes found
  during that pass were corrected and reverified.
- Device management revoked both an older active tablet credential and a pending
  diagnostic credential while leaving the current tablet credential active.
- The exact minified Big Orbit code-2 APK cold-launched without a fatal runtime event on both
  the API 36 tablet emulator and physical Pixel 8 Pro. The Pixel remained behind its secure
  keyguard, so this proves process startup but not physical UI interaction or enrollment.
- The tablet shell was checked at 1.3 font scale; the navigation rail width was
  increased so labels remain visible. Captured evidence stays ignored under
  `.inspect/` because it contains disposable test state rather than showcase
  material.

## Production rollout evidence

At the start of the rollout, production still served Little Orbit 1.1.1 phone code 26 and Wear
code 20, `/api/v2/admin/devices` was absent, and readiness returned HTTP 200.

- A fresh coordinated encrypted database/attachment pair completed at
  `2026-09-21T06:50:39.6579706Z`. It excluded raw coordinates, attributable quiz feedback, and
  anonymous raw reviews; no off-host copy was made.
- Production applied migrations through `0029`. PostgreSQL reported pgvector 0.8.6, all expected
  new table families existed, and API, web, worker, media worker, context fetcher, gateway,
  PostgreSQL, ClamAV, and Ollama reached their expected healthy/running states.
- Local and public `/admin` and `/api/v1/admin/configuration` returned 404. Unauthenticated
  `/api/v2/admin/devices` returned 403 without revealing protected state.
- The exact Big Orbit code-2 APK was installed on the Pixel and tablet and cold-launched on both.
  The owner waived production enrollment, cross-device revocation, alerts, and recovery proof as
  publication gates and will perform them as post-release QA.
- The exact signed phone APK upgraded the physical Pixel from code 26 to 28. The package UID and
  original install time were preserved, and pulling the installed base APK produced SHA-256
  `aaa8c98d452db6d87c687f25cd2630432b64481ab6753c2bdb7bdb5baa7dc04f`.
  The owner waived unlocked UI, account, pairing, and relationship-state observation.
- The physical Pixel Watch 3 remains installed on code 19. The published production wizard now
  offers the unchanged signed code-20 artifact; the owner will exercise that update as post-release
  QA, so this rollout does not claim a physical code-20 installation.
- The immutable API record was published at `2026-09-21T12:10:32.956306Z`, retained floor 23,
  and omitted `required_after`. Local and public complete phone/Wear downloads matched the
  manifest; all four 1,024-byte ranges returned 206 with correct totals.
- GitHub releases `littleorbit/v1.2.0` and `big-orbit/v1.0.0` are public, non-draft releases.
  Downloaded Big Orbit bytes and GitHub-reported Little Orbit asset hashes matched the verified
  artifacts. Public download, patch-notes, RSS, status, showcase, home, and readiness routes
  returned 200; rollout logs contained no traceback, unhandled, fatal, panic, or exception match.
- The daily encrypted-backup, Tuesday restore-drill, and typed admin-job tasks were registered.
  One runner backup recorded `passed|local_encrypted|false`; one non-destructive restore drill
  recorded `passed`, verified excluded private rows were empty, and removed its temporary database.

The owner also waived the off-host backup-copy/restore gate and durable off-host backup of the Big
Orbit signing key until the replacement server is available. None of the device or off-host
waivers above is evidence that those checks ran.
