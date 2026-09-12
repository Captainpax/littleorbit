# RC6 verification record — 2026-09-12

This record covers system insets, relationship age and nearby-time separation, device permissions, widget/Wear refresh, and first-party Wear delivery. Public deployment results are recorded only after each check succeeds.

## Release identity

- Release source commit: pending the final reviewed commit and immutable `v1.0.0-rc.6` tag.
- Phone APK: 15,907,162 bytes, SHA-256 `71093232e3d3dc5c0523a785ad9314de2fa14a0338ef5c9ae336962caa9033fc`.
- Wear APK: 14,124,686 bytes, SHA-256 `857197277ac5da7c23db816ae8dd04f95defa137c4870a0cb1ef2abbac086027`.
- Both APKs passed Android `apksigner` with signing-certificate SHA-256 `43e83a420c7496ce9121339ab5bd6b01a6357161a83a95042ace56855bd89337`.
- Both packages identify as `com.littleorbit.mobile`, version code 6, version name `1.0.0-rc.6`; phone requires API 29 and Wear requires API 30.
- The compatibility floor remains unchanged until the migration, both hosted artifacts, updater discovery, and public download checks pass.

## Automated checks

- Python: 57 API and AI tests passed; Ruff and strict mypy passed across 70 source files.
- Android: domain, data, phone, and Wear unit tests passed; data, phone, and Wear lint passed. The Room 3→4 migration instrumentation test compiled; no emulator was connected to execute it yet.
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

Pending final commit, backup, migration, container rebuild, publication, compatibility-floor activation, and public HTTP/range/hash checks.

## Remaining release gates

RC6 still needs the full two-phone and Wear OS physical-device or emulator flow: signup, pairing, mutual relationship date, all quiz formats, notification delivery, countdown, notes, location, widget, export, unpairing, updater recovery, large text, watch installation, tile, and complication. DHCP reservation, a clean-database backup restore drill, and final privacy/terms review also remain launch gates. RC6 remains a prerelease.
