# RC15 verification — 2026-09-15

## Scope

This record covers removal of hosted notification transport, the compatibility migration, signed Android artifacts, an API 36 upgrade rehearsal, and the production release checks recorded below. It does not claim instant background alerts: Android controls WorkManager timing when Little Orbit is not visible. It also does not close the complete two-physical-phone, tablet, widget, or watch journey.

## Self-hosted notification boundary

- Android, API, worker, dependency, secret, and Compose paths for Firebase Messaging were removed.
- Installations retain only a random Little Orbit UUID, notification permission and preference state, last-seen time, and per-installation acknowledgement state. No provider-issued notification address is accepted or stored.
- A visible app receives only `notification.available` through Little Orbit's authenticated WebSocket and then fetches authorized metadata through HTTPS. Background WorkManager polls that same self-hosted endpoint.
- RC14 request compatibility is limited to a null-only `push_token` field. A non-null value fails schema validation, responses report `push_enabled: false`, and the transport identifier is `self_hosted_wss_polling`.
- The phone dependency graph contains no Firebase Messaging artifact. The merged manifest and APK contain no Firebase provider, message service, messaging-event receiver, or FCM endpoint. Three generic `com.google.firebase` exception classes remain inside Google Play Services Basement, a transitive dependency of the required Wear Data Layer; they expose no notification transport.

## Automated and database evidence

- Ruff passed for `services/api` and `services/ai`.
- Strict mypy passed all 145 Python source files.
- The database-independent Python suite passed 134 tests with 26 environment-gated cases skipped.
- Android domain, data, mobile, widget, and Wear unit tests passed. Mobile and Wear debug lint passed.
- Ten API 36 instrumentation tests passed, including signed-out shell behavior, left-edge drawer navigation, crop approval visibility, safe Markdown, encrypted note restoration, and deletion of every retired hosted-transport preference.
- A clean disposable PostgreSQL database upgraded from `0001` through `0024`. At head it contained none of the seven retired provider fields or their partial index. Downgrading to `0023` restored exactly those objects, and re-upgrading removed them again.
- Twenty disposable PostgreSQL integration cases passed for per-installation notifications, partner-note synchronization, authorization, pairing, and RC14 security boundaries. The disposable database was removed afterward.

## Signed artifact evidence

| Artifact | Version code | Bytes | SHA-256 |
| --- | ---: | ---: | --- |
| Phone `1.0.0-rc.15` | 20 | 36,218,181 | `7d6157802710ef7515c40f823fe92cce0fad48c136ba92ec3b83a703c5971aa3` |
| Wear `1.0.0-rc.14` reused | 16 | 14,188,854 | `6ce385654e323dfdcad9d5b6dec000a4f2549568d30b604ce6ea1400d642f0b6` |

Both artifacts verify with certificate SHA-256 `43e83a420c7496ce9121339ab5bd6b01a6357161a83a95042ace56855bd89337`. The exact signed RC14 phone artifact installed on an API 36 emulator, upgraded in place to code 20, and remained running after a cold launch without a fatal Android log entry.

## Production and publication evidence

- A coordinated encrypted PostgreSQL and attachment snapshot completed before migration. Restoring that database into an isolated target found two notification installations, zero encrypted or hashed provider addresses, zero refresh, attempt, or success timestamps, zero accumulated failures, and two address-invalidation timestamps. The encrypted rollback snapshot remains under the documented 14-day retention; it contains no provider address. The isolated restore database was dropped after the aggregate check.
- Production upgraded transactionally to Alembic head `0024`. The active `notification_devices` table has zero `push_%` columns and no retired provider-address index.
- Rebuilt API and worker containers contain no `google-auth` module and expose no environment names containing `FIREBASE`, `FCM`, or `PUSH_TOKEN`. Migration, role-bootstrap, and grant jobs exited successfully; the API, web, gateway, PostgreSQL, Ollama, and ClamAV reported healthy.
- A second coordinated encrypted backup completed after migration and excludes raw coordinates, giving recovery coverage for the provider-free schema.
- Local gateway and public API readiness returned `200` after deployment. Recent migration, API, and worker logs contained no error, fatal traceback, Firebase, or FCM match.
- Fresh isolated smoke accounts paired successfully. Partner document creation, listing, bidirectional live edits, disconnect/reconnect catch-up, and final revision convergence passed. Smooch delivery, the content-free first-party WebSocket hint, two-installation acknowledgement isolation, and the 30-minute document-edit cooldown passed. The isolated stack, volumes, accounts, and credential file were removed afterward.
- The authorized physical Pixel upgraded in place from the exact signed RC14 code 19 APK to signed RC15 code 20 without clearing app data. It remained running after a cold launch and produced no Little Orbit fatal Android log entry.

- The API published the immutable RC15 record at `2026-09-15T04:45:08.326115Z` with phone code 20, Wear code 16, compatibility floor 6, and the analyzed sizes, hashes, package, and certificate.
- Public `HEAD` requests returned the exact phone and Wear byte counts with byte-range support. Independent complete streams produced 36,218,181 phone bytes and 14,188,854 Wear bytes with the exact signed SHA-256 values. A 1,024-byte request for each artifact returned `206` and the exact total in `Content-Range`.
- Public `/download`, `/patch-notes`, and `/patch-notes.xml` returned `200`, named RC15, and the RSS response used `application/rss+xml`. The GitHub prerelease mirrors all five expected assets with exact APK byte counts.
- Local and public API readiness remained `200`, all long-running production services remained up, and no new host port was exposed.
