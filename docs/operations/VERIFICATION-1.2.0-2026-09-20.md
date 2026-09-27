# 1.2.0 quiz intelligence and Big Orbit verification — 2026-09-20

This record covers the initial implemented 1.2.0 source candidate. It is not a publication record. Phone code 27 was later signed and discarded before publication after QA-only bytecode was found during deep release inspection; the replacement candidate is code 28. Wear remains unchanged at 1.1.1 code 20.

## Implemented evidence

- The public web administrator UI and proxy were removed. The production web build exposes no `/admin` route, and the public-site end-to-end specification now requires `/admin` to return 404.
- Quiz protocol v3, launch-forward shared-reveal feedback, author-private reviews, 30-day unlinking, 90-day raw-review deletion, thresholded aggregates, weekly learning, database and same-batch semantic duplicate checks, and atomic policy activation are represented in the API, AI service, migration, protocol fixtures, Android client, and documentation.
- Administrative HTTP routes moved to `/v2/admin`. They require an enrolled P-256 device credential, a signed challenge, a device-bound session, and the existing password and MFA proofs. `/v1/admin` is not registered.
- Public context retrieval is limited to source keys and URLs compiled into the service. The fetcher rejects redirects, non-HTTPS destinations, private or loopback resolution, unsupported media, oversized responses, and instruction-like content before the AI boundary.
- Operations jobs use typed database records and a fixed dispatcher. They cannot supply commands, URLs, or filesystem paths. Backup output excludes raw and attributable quiz-feedback tables, binds the exact encrypted database and attachment artifacts in an atomic pair manifest, and promotes optional off-host copies only after hash verification. The restore drill uses that exact pair, a new exact-name temporary database, and streamed attachment verification.
- Five generated concept sheets are stored under `docs/concepts/1.2.0/` and are explicitly labelled as concepts rather than production screenshots.

## Automated verification

- `python -m ruff check services` passed.
- `python -m mypy services` passed with no issues in 181 source files.
- `python -m pytest services/api/tests services/ai/tests` passed with 168 tests, 32 skips, and 14 pre-existing framework/OpenAPI warnings. The skips include database-backed coverage that requires `LITTLE_ORBIT_TEST_DATABASE_URL`.
- `python infra/scripts/check_quality.py` passed the ratcheted 500-logical-line, 60-line-function, and cyclomatic-complexity limits for all 464 source files. Scheduled quiz persistence was separated from worker orchestration during this audit.
- `python -m little_orbit_ai.evaluate` passed: all seven future dates retained five safe fallback questions.
- `npm --prefix apps/web run check` passed lint, strict type checking, 34 Vitest tests, and the Next.js production build. The generated route inventory contained no `/admin` route.
- `gradlew :apps:android:domain:test :apps:android:data:testDebugUnitTest :apps:android:mobile:testDebugUnitTest :apps:android:mobile:lintDebug --no-daemon` passed 121 tasks.
- `gradlew -PmobileTestBuildType=smoke :apps:android:mobile:verifyWearArtifactIsolation :apps:android:mobile:connectedSmokeAndroidTest --no-daemon` passed 218 tasks on the API 36 tablet emulator. Wear artifact isolation remained intact for this phone-only release.
- Compose configuration rendering passed. Alembic offline SQL generation passed specifically for the new `0026:head` pgvector-backed migration range; full-history offline rendering remains unsupported by the pre-existing live-data backfill in migration 0018.
- Every PowerShell file in `infra/scripts/` parsed successfully. The attachment backup verifier compiled successfully. The new backup, restore, and scheduler scripts were not run against durable data.
- `python infra/scripts/check_docs.py` passed after the repository Markdown inventory was updated.

## Big Orbit repository and Android evidence

- The independent public repository is [Captainpax/big-orbit](https://github.com/Captainpax/big-orbit), initialized on `main` at commit `3106223` and documented at head `e6600bd`. The verified app source includes `388da36` for race-safe local sign-out and stopped signed-out polling, plus `6829c60` for native question-report decisions, service health, registration controls, bounded account/session actions, and security-event visibility.
- Big Orbit uses package `com.littleorbit.bigorbit`, version 1.0.0 code 1, Java 17/XML, an independent signing configuration, protected non-exportable device keys, encrypted local session state, generic local notifications, and no Firebase dependency.
- The smoke package is `com.littleorbit.bigorbit.smoke`, version `1.0.0-qa` code 1, with an explicit Big Orbit QA label and loopback-only development endpoint.
- `gradlew :app:testDebugUnitTest :app:lintSmoke :app:assembleSmoke --no-daemon` passed 66 tasks. Lint reported no errors.
- The merged release manifest was inspected: production package and label were correct, backup was disabled, cleartext traffic was disabled, and no smoke package, QA label, or QA endpoint marker was present.
- The smoke APK was 18,344,145 bytes with SHA-256 `3F46536B557FA0AA45BF44CA493D88D4BF95E4306B3063155195D90B2D0B6F38`.
- That smoke APK installed side by side on the API 36 tablet emulator and cold-launched successfully in 1,536 ms after installation optimization. Application exit history contained only package-update stops and no matching crash or ANR. The repository screenshot is simulated and contains no administrator credentials.
- The committed repository excludes `local.properties`, build directories, keystores, passwords, and private keys. A secret-pattern review found none of the checked token, private-key, or signing-password forms.

## Open release gates

- The PostgreSQL integration suite, including the three new feedback tests, still needs a disposable database running the pinned pgvector image. Offline migration rendering is not a substitute for applying, exercising, and reversing the migrations.
- The Little Orbit web Playwright suite was updated but not run against a freshly built 1.2.0 stack in this verification pass.
- Big Orbit enrollment, challenge login, MFA, revocation, notification polling, and every console action still need end-to-end testing against a disposable 1.2.0 API. The tablet observation covered installation and rendering only.
- Saturday learning, Sunday generation, semantic reserve behavior, live allowlisted context retrieval, retry recovery, and threshold transitions still need clock-controlled PostgreSQL integration and worker testing.
- The encrypted backup, optional off-host copy, daily scheduler, Tuesday restore drill, typed job dispatcher, and audit evidence still need a disposable runtime exercise. No production backup or database was modified.
- Physical Pixel phone accessibility, large-font, feedback editing/deletion, notification, and Big Orbit flows remain unobserved. This release intentionally makes no Wear code or package change.
- No signed Little Orbit 1.2.0 APK, release manifest, immutable artifact hashes, upgrade test, production deployment, or GitHub release exists. Version codes and bytes must not be published until all required gates pass.

The source implementation is therefore a testable 1.2.0 candidate, not a shipped release. A later verification record must capture the missing database, operations, physical-device, signed-artifact, upgrade, and publication evidence without rewriting this record.
