# 1.3.0 implementation verification — 2026-09-23

This record describes local source verification only. It is not a signed-artifact, physical-device, production-deployment, or publication claim.

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

## Security and privacy checks represented in tests

- Bootstrap PINs are eight digits, hash-only, single-use, ten-minute capabilities with five-attempt invalidation and one active setup per administrator.
- Restricted bootstrap tokens cannot substitute for ordinary device-bound administrator sessions; P-256 challenge messages use the separate `bootstrap` purpose.
- Reserve cardinality is exactly 1,825 general plus 365 intimacy entries with unique stable identities and hashes.
- Weekly plans require Monday start, seven ordered unique daily themes, and no more than two observances. Scheduling tests cover the configured local hour and daylight-saving behavior.
- Learned policy activation is schema- and evaluation-gated; rejected or instruction-shaped output remains audit metadata and cannot become active.
- Global questions retain exact, trigram, concept-family, and embedding duplicate gates; model candidates fail closed when semantic verification is unavailable.
- Big Orbit receives content-free operational state only. No account token, quiz answer, note, relationship content, review author, precise location, or arbitrary command input was added.

## Open gates

- Build and inspect exact signed phone, Wear, and Big Orbit candidates. Do not reuse a failed version code or byte sequence.
- Exercise fresh, returning, expired, wrong-PIN, fifth-failure, process-death, malformed-QR, first-MFA, and existing-MFA flows on real Big Orbit devices.
- Exercise the v4 quiz UI, large text, theme fallback, offline/retry behavior, and two-partner feedback privacy on the physical phone/tablet matrix.
- Upgrade the physical phone and watch, verify data preservation and passive surfaces, then run production migrations only after a coordinated encrypted backup.
- Publish immutable metadata and exact mirrored bytes only after all remaining gates pass or an owner waiver is recorded explicitly. No such waiver or publication is claimed here.
