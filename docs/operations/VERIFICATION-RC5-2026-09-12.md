# RC5 verification record — 2026-09-12

This record covers the RC5 daily-quiz and local-AI release. The [RC4 record](VERIFICATION-2026-09-12.md) covers the first-party resumable APK path that RC5 continues to use.

## Release identity

- Release source commit: `816cd4c`, tagged with the immutable annotated tag `v1.0.0-rc.5`.
- Phone APK: 15,823,790 bytes, SHA-256 `044c7c068fde480407ed3f1d29ec7df4bdf19d1b855e334f4e30a769732848ed`.
- Wear APK: 14,121,514 bytes, SHA-256 `d027f691d211bb267c615a74f1901cef4f48f2f216324e235f3330422d2bb08a`.
- Both APKs passed Android `apksigner` with signing-certificate SHA-256 `43e83a420c7496ce9121339ab5bd6b01a6357161a83a95042ace56855bd89337`.
- Two consecutive signed builds produced byte-identical phone and Wear artifacts.
- The GitHub prerelease contains the matching phone and Wear APKs and checksum sidecars.
- The published API record is immutable and identifies RC5, version code 5, Android API 29 minimum, exact phone byte count, APK hash, package, signing certificate, and first-party download URL.

## Quiz and privacy behavior

- A disposable two-account integration run exercised a stable five-question daily snapshot, private drafts, duplicate-operation idempotency, stale-revision rejection, hidden partner answers, reopen and edit, and atomic reveal after both partners finished.
- The same run exercised FIFO custom-question scheduling for the next eligible UTC day. Test accounts and their data were removed after the run.
- An isolated PostgreSQL transaction verified that either partner's intimacy opt-out replaces every unrevealed intimacy prompt, removes affected drafts, resets completion, preserves five unique questions, and increments the snapshot revision. The transaction was rolled back after the assertion.
- Pending shared custom questions expose prompt details to both partners; surprise questions expose only their count until scheduled.
- Android's content-free status worker retrieves completion state only. Quiz prompts and answers are fetched while the user is actively using the app.
- Client compatibility enforcement includes both `/v1/quizzes` and `/v2/quizzes`. A public RC4 request to the RC5 quiz route returned `426`; the same unauthenticated request identifying as RC5 passed the version gate and reached authentication, returning `401`.

## Local AI and future coverage

- Ollama loaded `qwen3:4b-instruct-2507-q4_K_M` through NVIDIA CUDA, with all 37 model layers on the GPU and an approximately 2.376 GiB model buffer.
- A live adapter probe returned ten schema-valid candidates in approximately 29 seconds.
- The AI pipeline validated structured shape, content safety, option and rating bounds, category rules, and recent-question similarity before publication.
- Candidate batches with the wrong requested mix are retained with a `candidate_mix_invalid` validation result instead of being treated as a transport failure.
- Seven future UTC dates were populated. When too few Ollama candidates survived validation, the scheduler filled the remaining positions from the curated bank and recorded the fallback reason.
- The 1.0 prompt contains no account, couple, answer, note, email, location, or relationship data.

## Automated checks

- Python: 50 API and AI tests passed; Ruff and strict mypy passed across 66 source files.
- Android: domain, data, and mobile unit tests passed; phone and Wear lint passed; Wear has no unit-test source set yet.
- Web: ESLint, strict TypeScript, 15 Vitest tests, and the Next.js production build passed.
- Repository: source-size and complexity checks passed across 178 files; documentation links and diff whitespace checks passed.
- Database migration `0009` reached the current Alembic head. A pre-migration PostgreSQL backup was written to `backups/postgres/little-orbit-20260912-082115.dump`.

## Public deployment

- `https://lil-orb.pax-kun.com/api/v1/health/live` returned `200` through Nginx Proxy Manager and the gateway.
- The first-party APK endpoint returned `200` to `HEAD`, `Content-Length: 15823790`, byte-range support, immutable caching, and the published digest ETag.
- A request for bytes 0 through 1023 returned `206`, exactly 1,024 bytes, and `Content-Range: bytes 0-1023/15823790`.
- A complete public download returned 15,823,790 bytes and matched the published phone SHA-256 exactly.
- The public download page displayed RC5 and the matching checksum.
- Gateway, web, PostgreSQL, and Ollama were healthy after deployment; the API answered public health and compatibility probes and the worker was running.

## Remaining release gates

RC5 has not completed the required real-device flow on two Android phones and a Wear OS device or emulator. Physical checks still include signup, pairing, all quiz formats, waiting and reveal, custom questions, notifications, countdowns, notes, location, widgets, export, unpairing, interrupted update recovery, large text, and Wear surfaces. DHCP reservation, backup restoration on a clean database, and final privacy and terms review also remain launch gates. RC5 therefore remains a prerelease.
