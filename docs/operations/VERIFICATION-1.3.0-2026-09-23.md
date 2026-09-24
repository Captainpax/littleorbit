# 1.3.0 implementation verification — 2026-09-23

This record covers source verification, exact signed artifacts, emulator cold launches, and the pre-migration production backup. It is not a physical-device, production-migration, or publication claim unless a later section records that evidence explicitly.

## Verified locally

- Little Orbit and Big Orbit version-contract checks agree on release train 1.3.0, phone code 29, Wear code 21, and Big Orbit code 3.
- Ruff and Mypy pass across 205 Python source files. The repository quality ratchet passes all 493 checked Java, Python, TypeScript, and TSX source files.
- The complete Python suite passes with 193 tests and 38 environment-dependent skips. The skips include tests that intentionally require an explicitly named disposable PostgreSQL database.
- The standalone AI evaluation passes: seven future dates each retain five safe fallback questions without requiring Ollama.
- Strict v4 generated-question and delivered-quiz schemas accept their valid fixtures and reject invalid fixtures in Python, Android, and web tests.
- The web `npm run check` passes lint, strict TypeScript, 40 Vitest cases, and the optimized Next.js production build. All 16 Playwright cases pass across desktop and mobile projects, including explicit 404 checks for both retired public administrator routes.
- Little Orbit mobile and Wear debug unit tests, lint, and debug assembly pass: 185 Gradle tasks completed successfully. Big Orbit debug unit tests, debug lint/assembly, and smoke lint/assembly pass: 90 Gradle tasks completed successfully.
- The dedicated Wear artifact-isolation task passes after building both phone variants: the ordinary debug APK contains no bundled QA Wear APK, while the smoke APK contains its exact trusted generated smoke companion.
- Big Orbit Java compilation also passes after the malformed-QR recovery change. Its existing `ConsoleActivity` deprecation note remains non-fatal and unrelated to this release scope.
- Complete Markdown/link inventories pass for both repositories, final diffs pass whitespace validation, and the exact disposable migration database was deleted after its rerun. Build products remain ignored rather than added to source control.

## Disposable PostgreSQL evidence

An exact isolated PostgreSQL/pgvector database completed migration `0001 -> 0031 -> 0029 -> 0031`. After the final bootstrap refactor, optional bootstrap and reserve integration tests passed all three cases again: first-owner PIN consumption through key proof and TOTP completion, fresh signed credential recovery after a lost completion response, invalidation of an older live setup capability by a new PIN, and transactional one-use reserve consumption. The exact `little_orbit_13_migration_test` database was then dropped; only the ordinary disposable smoke database remains.

## Exact signed artifacts

| Artifact | Package | Version code | Bytes | SHA-256 |
| --- | --- | ---: | ---: | --- |
| Little Orbit phone | `com.littleorbit.mobile` | 29 | 37,696,175 | `c5c879d458719e3ed27e5bdda38823d839600141ca08ff0d8967356df0d623e9` |
| Little Orbit Wear | `com.littleorbit.mobile` | 21 | 14,737,944 | `0f0f0f221d80bbb5fc9db70773d8980b5b40136251df2fe4e64c8b3530e985cf` |
| Big Orbit | `com.littleorbit.bigorbit` | 3 | 2,485,190 | `deccc454920c08793b3ce56b570b5c049343a48a7008984d7de0f91713ea8a5b` |

The phone and Wear APKs use pinned certificate SHA-256 `43e83a420c7496ce9121339ab5bd6b01a6357161a83a95042ace56855bd89337`; Big Orbit uses its independent pinned certificate `04dc3502933faaa99dfd6641acc52b2bd71c9895087cb3060e3ce92dd8406f8c`. `apksigner`, `aapt`, and fresh SHA-256/byte-count calculations agreed with both generated verification records. All three APKs are non-debuggable, target API 36, disable Android backup, and contain none of the checked smoke packages, QA labels, loopback QA endpoints, or bundled smoke-Wear names.

The exact phone and Big Orbit APKs fresh-installed beside the preserved Little Orbit smoke package on an API 36 emulator and cold-launched with live processes and no matching fatal exception or ANR. The exact Wear APK fresh-installed on the dedicated 454x454 API 34 emulator, reached the expected relationship-unavailable screen, and had no matching fatal exception or ANR. These checks do not establish in-place physical upgrades, hardware transport behavior, or production enrollment.

## Pre-migration production protection

Production was healthy on migration head 0029 and still advertised 1.2.0 before rollout. A coordinated encrypted database/attachment backup completed and the latest pair passed the non-destructive restore drill: schema verified, excluded private rows verified empty, and the attachment manifest verified. The first Windows PowerShell 5.1 run exposed use of a newer .NET relative-path API after encrypted component creation but before pair-manifest creation. The coordinator was repaired with a workspace-bounded compatibility helper, rerun successfully through the documented `powershell.exe` path, and its newest pair passed the restore drill. The earlier encrypted orphan components were not treated as a completed pair.

## Security and privacy checks represented in tests

- Bootstrap PINs are eight digits, hash-only, single-use, ten-minute capabilities with five-attempt invalidation and one active setup per administrator.
- Restricted bootstrap tokens cannot substitute for ordinary device-bound administrator sessions; P-256 challenge messages use the separate `bootstrap` purpose.
- Reserve cardinality is exactly 1,825 general plus 365 intimacy entries with unique stable identities and hashes.
- Weekly plans require Monday start, seven ordered unique daily themes, and no more than two observances. Scheduling tests cover the configured local hour and daylight-saving behavior.
- Learned policy activation is schema- and evaluation-gated; rejected or instruction-shaped output remains audit metadata and cannot become active.
- Global questions retain exact, trigram, concept-family, and embedding duplicate gates; model candidates fail closed when semantic verification is unavailable.
- Big Orbit receives content-free operational state only. No account token, quiz answer, note, relationship content, review author, precise location, or arbitrary command input was added.

## Open gates and owner direction

- Apply production migrations 0030 and 0031, verify knowledge/reserve synchronization and healthy workers, then publish immutable API metadata and exact GitHub mirror bytes.
- Verify current metadata, patch notes, RSS, local/public readiness, complete downloads, and 1,024-byte ranged downloads against the exact hashes above.
- Exercise fresh, returning, expired, wrong-PIN, fifth-failure, process-death, malformed-QR, first-MFA, and existing-MFA flows on real Big Orbit devices.
- Exercise the v4 quiz UI, large text, theme fallback, offline/retry behavior, and two-partner feedback privacy on the physical phone/tablet matrix; upgrade the physical phone and watch and verify preservation/passive surfaces.

On 2026-09-23 the owner asked for the signed update to be released as soon as possible and will perform the physical-device checks as live QA after publication. Publication may proceed only after the automated, exact-artifact, encrypted-backup/restore, migration, and public-verification gates pass. This direction defers the listed hardware observations; it does not convert them into passed evidence.
