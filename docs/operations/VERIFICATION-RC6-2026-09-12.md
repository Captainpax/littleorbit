# RC6 verification record — 2026-09-12

This record covers system insets, relationship age and nearby-time separation, device permissions, widget/Wear refresh, and first-party Wear delivery. Public deployment results are recorded only after each check succeeds.

## Release identity

- Release source commit: `65bd0ea9fa918aae64a2c5c10362f8424f2435aa`, preserved by immutable tag `v1.0.0-rc.6`.
- Phone APK: 15,907,162 bytes, SHA-256 `71093232e3d3dc5c0523a785ad9314de2fa14a0338ef5c9ae336962caa9033fc`.
- Wear APK: 14,124,686 bytes, SHA-256 `857197277ac5da7c23db816ae8dd04f95defa137c4870a0cb1ef2abbac086027`.
- Both APKs passed Android `apksigner` with signing-certificate SHA-256 `43e83a420c7496ce9121339ab5bd6b01a6357161a83a95042ace56855bd89337`.
- Both packages identify as `com.littleorbit.mobile`, version code 6, version name `1.0.0-rc.6`; phone requires API 29 and Wear requires API 30.
- The compatibility floor activated at `2026-09-12T17:45:00Z`, after migration, both hosted artifacts, updater discovery, and public download checks passed.

## Automated checks

- Python: 57 API and AI tests passed; Ruff and strict mypy passed across 70 source files.
- Android: domain, data, phone, and Wear unit tests passed; data, phone, and Wear lint passed. Two Room migration instrumentation tests then passed on an API 36 emulator.
- Web: ESLint, strict TypeScript, 15 Vitest tests, and the Next.js production build passed. The project Playwright suite passed 12 desktop/mobile flows after release-test drift was corrected.
- Repository quality limits, documentation links, Markdown lint, and whitespace checks passed. Two consecutive signed builds produced the same phone and Wear hashes.
- A disposable PostgreSQL database upgraded from 0001 through 0010, matched SQLAlchemy metadata with no pending operations, downgraded to 0009, and upgraded to 0010 again. This check found and fixed the original dynamic-model bootstrap migration before production.
- The in-app browser connection was unavailable. Rendered browser coverage therefore comes from the repository Playwright projects rather than an attached interactive tab.

## Behavior covered

- All phone activities use one additive system-bar, display-cutout, navigation-bar, and keyboard inset policy. The home cards no longer use negative margins.
- Relationship age comes from a shared start date with proposer/partner roles, idempotent operations, a seven-day expiry, a database uniqueness constraint, and conflict responses for stale decisions.
- Nearby time uses deterministic one-to-one matching, two confident endpoints, a maximum twenty-minute gap, minute-bucket overlap protection, and a separate stale process time.
- Location uploads require mutual server consent; either opt-out deletes both partners' raw samples. Android also requires precise foreground and background permissions and rejects fixes older than two minutes.
- Notification channels are created at startup. Quiz polling runs only while signed in and permitted, and the first observed server state establishes a baseline without a false notification.
- Widget and Wear caches keep relationship age, nearby estimate, countdown, process time, and sync time separate. Widget refresh, sign-out clearing, Wear v2 sync, tile, and complication unit behavior are covered.
- More and the guided setup screen distinguish notification permission, local location permission, mutual location consent, connected watch, and installed watch app state.
- The Wear installer verifies release authority, byte count, SHA-256, package, version, device type, and pinned signer before wireless ADB installation.

## Public deployment

- A production PostgreSQL backup was created at `backups/postgres/little-orbit-20260912-101954.dump` before migration.
- API startup upgraded production from 0009 to 0010. API, web, worker, gateway, PostgreSQL, and Ollama were running; exposed services reported healthy.
- GitHub prerelease `v1.0.0-rc.6` contains both exact APKs and checksum sidecars.
- The public metadata feed returned every expected phone and Wear field. HEAD requests returned the exact sizes, immutable cache policy, byte-range support, and checksum headers.
- `0-1023` range requests returned `206` with correct `Content-Range` values. Complete public phone and Wear downloads matched the signed build byte counts and SHA-256 values.
- The live desktop/mobile Playwright suite passed all 12 flows. The download page displayed RC6 and Wear content, and the public watch installer returned `200`.
- A WSS upgrade reached the API authentication boundary through Nginx Proxy Manager and the gateway.
- Before activation, version codes 5 and 6 both reached authentication. After activation, code 5 returned `426 client_update_required` with floor 6 while code 6 reached authentication.
- The bug hunt found that `/v2/together-time` was absent from the compatibility route list. Commit `88c7db3` added it, passed 57 Python tests plus Ruff and strict mypy, deployed before floor activation, and passed CI.
- The signed RC6 phone cold-launched on an API 36 emulator with clear status and navigation areas. A round Wear OS 5 emulator then exposed clipped fallback text; immutable RC6 was preserved and the correction moved to RC7.

## Remaining release gates

RC6 still needs the full two-phone and Wear OS physical-device or emulator flow: signup, pairing, mutual relationship date, all quiz formats, notification delivery, countdown, notes, location, widget, export, unpairing, updater recovery, large text, watch installation, tile, and complication. DHCP reservation, a clean-database backup restore drill, and final privacy/terms review also remain launch gates. RC6 remains a prerelease.
