# Little Orbit 1.0.1 verification — 2026-09-19

This living release-gate record covers the Together Time and Our Space
reliability update. It distinguishes source and synthetic verification from
isolated PostgreSQL, physical-device, signed-artifact, and production evidence.

## Verified implementation

- The chronological estimator supports later-confirmed bridges of at most 20
  minutes, rejects an intervening apart or poor-accuracy observation, records
  observed and bridged seconds separately, and leaves live projection capped
  at five minutes of mutually fresh evidence.
- Android requests collection recovery after foreground-service and network
  recovery without transmitting SSID, BSSID, IP address, or another network
  fingerprint.
- History and corrections use the couple's IANA home timezone and compute the
  actual local-day duration, including daylight-saving transition days.
- Diagnostics are separately opted in by installation, contain no coordinates
  or network identifiers, expose no installation identifier to the partner,
  expire within 24 hours, and are purged on opt-out or relationship end.
- Note creation, title changes, and body changes share one serialized mutation
  path. One creation identity is persisted before the first request, autosave
  coalesces edits, and a newer server revision requires an explicit conflict
  decision.
- Explicit note forks reauthorize the active couple, map only clean attachments
  owned by the source note, reserve quota, verify sanitized bytes, and rewrite
  attachment references. Conservative duplicate archival requires a verified
  encrypted backup sidecar.
- Animated GIF rendering preserves animation and presents pause/play behavior;
  Android reduced-motion state starts the animation paused.

## Automated checks

| Check | Result |
| --- | --- |
| Focused API proximity, history, and duplicate tests | Passed, 25 tests in the final focused rerun |
| API Ruff | Passed |
| API strict mypy | Passed, 149 source files |
| Full API pytest | Passed, 141 tests; 29 environment-gated tests skipped |
| Isolated PostgreSQL migration/concurrency/retention suite | Passed, migration through 0026 and 29 tests |
| Backup/migration/maintenance rehearsal | Passed with a verified age-encrypted disposable backup; one retained history rebuilt and zero safe duplicates archived |
| Complete Android unit and lint matrix | Passed; final mobile unit/lint rerun also passed |
| Android API 36 instrumentation | Passed, 11 mobile and the data Room migration suite |
| Disposable paired-account emulator smoke | Passed, including note-fork retry safety, attachment remapping, inline PNG/GIF rendering, and GIF pause/play |
| Release-signed physical Pixel upgrade | Passed from code 23 to 24; cold launch completed without an Android runtime crash |
| Repository size and complexity limits | Passed, 420 source files |
| Compose configuration resolution | Passed |
| Documentation inventory and Markdown lint | Passed, 105 repository-owned Markdown files and zero lint findings |

The skipped API cases require an explicitly disposable
`LITTLE_ORBIT_TEST_DATABASE_URL`. The normal suite did not substitute a local,
smoke, or production database.

## Artifact and rollout gate

The release-signed phone artifact is version `1.0.1` code 24, 37,563,270
bytes, with SHA-256
`c5856820ad186be616027c95b008a1d81edbe8c60dc7b2cc7301b13efa369c25`.
The unchanged Wear `1.0.0` code 18 artifact remains 14,189,878 bytes with
SHA-256
`43068ae14877ee0e158f6498a66f5987d56642521a8c4109372434e8c7fe9cd3`.
Both independently report release signing certificate SHA-256
`43e83a420c7496ce9121339ab5bd6b01a6357161a83a95042ace56855bd89337`.

The Motorola tablet was not connected during this run. The owner explicitly
waived that physical two-device soak on 2026-09-19 and authorized production
promotion while preserving the missing evidence in this report. The
compatibility floor remains code 23 during optional rollout.

## Production evidence

- An age-encrypted coordinated production backup completed before data
  maintenance. Its PostgreSQL and attachment hashes match their sidecars; the
  PostgreSQL sidecar records both raw locations and device-health rows as
  excluded.
- Migration `0026` is the production Alembic head. The API, worker, media
  worker, and website were recreated from the 1.0.1 source images. API and web
  health checks pass and the post-deployment error-log scan is clear.
- Retained coordinate-free history reaggregation rebuilt one eligible couple.
  The privacy-safe note classifier found two exact safe duplicates and no
  ambiguous groups, archived those two documents for normal seven-day
  recovery, and then reported zero remaining groups.
- Immutable release metadata was published at
  `2026-09-19T18:19:24.932834Z` with phone code 24, Wear code 18, compatibility
  floor 23, and no forced-update deadline.
- Local and public current-release responses agree. Complete phone and Wear
  downloads match the signed byte counts and SHA-256 digests. Both 1,024-byte
  range requests returned `206` with the exact total sizes.
- `/download`, `/patch-notes`, `/patch-notes.xml`, `/status`, `/showcase`, and
  public readiness returned `200`; RSS lists Little Orbit 1.0.1 first.
- The public GitHub release is
  <https://github.com/Captainpax/littleorbit/releases/tag/v1.0.1>.

The production backup initially exposed that the binary streaming helper used
the newer `.NET` `ProcessStartInfo.ArgumentList` API, which is absent from
Windows PowerShell 5.1. The helper now builds a correctly quoted native command
line on that host; the successful encrypted backup and matching hashes verify
the repair.
