# Local development

## Requirements

- Docker Desktop with Compose 5+
- Node.js 24+ and npm 11+
- Python 3.12 or 3.13 (the pinned native dependencies do not yet support 3.14)
- Java 17, Android SDK 37, and an Android emulator for client work

Copy `.env.example` to `.env` and replace every `change-me`, `replace-`, and placeholder repository URL. Development may use localhost URLs and Mailpit. Never reuse these values publicly.

```powershell
docker compose --env-file .env -f infra/compose.yaml -f infra/compose.dev.yaml config
docker compose --env-file .env -f infra/compose.yaml -f infra/compose.dev.yaml up --build
Invoke-WebRequest http://localhost:8180/api/v1/health/ready
```

Open `http://localhost:8180` for the website and `http://localhost:8025` for development email. Stop containers with `docker compose --env-file .env -f infra/compose.yaml -f infra/compose.dev.yaml stop`; do not delete volumes during routine work.

The first model initialization downloads roughly 2.5 GB. Add `-f infra/compose.gpu.yaml` only after NVIDIA container support works in Docker Desktop. CPU fallback is slower but retains curated-question coverage.

## RC14 API security checks

The normal API suite runs the pure security-boundary tests and skips destructive PostgreSQL integration cases unless an isolated database URL is supplied. The integration fixture truncates every application table before each case, so it must point only at a disposable test database created for this run. Never use a development, smoke, staging, or production database.

```powershell
.\.venv313\Scripts\python.exe -m pytest services\api\tests\test_security_rc14.py
$env:LITTLE_ORBIT_TEST_DATABASE_URL = "<isolated postgresql+asyncpg test URL>"
.\.venv313\Scripts\alembic.exe -c services\api\alembic.ini upgrade head
.\.venv313\Scripts\python.exe -m pytest services\api\tests\test_security_rc14_postgres.py services\api\tests\test_auth_enumeration_postgres.py services\api\tests\test_notifications_postgres.py services\api\tests\test_location_retention_postgres.py
Remove-Item Env:LITTLE_ORBIT_TEST_DATABASE_URL
```

The test harness copies `LITTLE_ORBIT_TEST_DATABASE_URL` into `DATABASE_URL` before importing the application. Its fixtures truncate every application table; the explicit URL must therefore name only a disposable database. Migration `0017` adds capped hashed throttle buckets and a separate encrypted pending administrator-MFA factor. Migration `0020` historically added hosted wake addressing; migration `0024` removes its index and every address or attempt column. Exercise a clean upgrade through the current head plus `0023 -> 0024 -> 0023 -> 0024`, then verify limit expiry/capping, reset-link family invalidation, deleted-account login rejection, current-factor proof for MFA replacement, old-session revocation, configuration allowlisting, pairing eligibility under locks, one-sided legacy-answer hiding, revoked-session note mutation rejection, independent notification acknowledgements, legacy migration, delivery-backfill races, strict hosted-address rejection, unpair purge, and raw-location deletion through both the declared expiry and absolute 24-hour predicates.

## Isolated paired-account smoke stack

Use the RC smoke project when Android needs real paired accounts, attachment processing, and Mailpit without touching hosted data or volumes. It binds the gateway to `127.0.0.1:18180` and Mailpit to `127.0.0.1:18025`; PostgreSQL, attachment bytes, and ClamAV definitions receive Compose-project-specific volumes. The development override explicitly clears Gmail credentials and production TLS settings before Mailpit starts.

```powershell
.\infra\scripts\smoke-stack.ps1 up
.\.venv313\Scripts\python.exe infra\scripts\create_smoke_couple.py
.\.venv313\Scripts\python.exe infra\scripts\note-sync-smoke.py
.\.venv313\Scripts\python.exe infra\scripts\create_attachment_smoke.py
.\.venv313\Scripts\python.exe infra\scripts\note-fork-smoke.py
.\.venv313\Scripts\python.exe infra\scripts\notification-smoke.py
.\gradlew.bat :apps:android:mobile:assembleSmoke
.\infra\scripts\android-smoke.ps1 -Serial emulator-5554 -AccountIndex 0 -ResetApp
.\infra\scripts\smoke-stack.ps1 down
```

The account generator creates unique `@example.com` accounts, consumes their Mailpit verification links, confirms a pair, and writes credentials only to ignored `.inspect/smoke-accounts.json`. The note-sync smoke creates a document as the first partner, requires the second partner to list it, exercises live edits in both directions, disconnect/reconnect catch-up, and identical final snapshots. The attachment seed uploads a synthetic transparent PNG and animated GIF through the private scan/sanitize pipeline, inserts their `attachment://` links, and records a unique ignored document title so repeated runs cannot select a stale fixture. The notification smoke verifies a content-free foreground hint, independent delivery and acknowledgement for two installations, legacy Smooch suppression, note-edit cooldown, and partner-viewing suppression. The Android smoke build targets the loopback gateway through `adb reverse tcp:18180 tcp:18180`. Its script signs in, checks the responsive shell, opens that exact synthetic attachment note, verifies both sanitized attachments, switches from preview to the Markdown dock, and stores an ignored screenshot. Run it sequentially on API 29, API 30, API 36 phone, and a wide API 36 tablet. Launch the Wear debug APK separately on the API 34 watch emulator and check the explicit stale fallback. Never point this workflow at the production Compose project.

## Quiz feedback and Big Orbit development

Run migrations `0027` and `0028` only against the smoke or another disposable PostgreSQL 17/pgvector database. The optional integration suite refuses to run unless `LITTLE_ORBIT_TEST_DATABASE_URL` names that exact target. Exercise pre-rollout questions, incomplete quizzes, custom questions, partner feedback lookup, replayed and conflicting operation IDs, revision conflicts, day-30 unlinking, day-90 review deletion, and the five-account aggregation threshold.

```powershell
$env:LITTLE_ORBIT_TEST_DATABASE_URL = "postgresql+asyncpg://.../little_orbit_test"
python -m pytest services/api/tests/test_quiz_feedback_postgres.py
```

Build the separate sibling project without sharing Little Orbit signing values:

```powershell
cd ..\big-orbit
.\gradlew.bat test lintSmoke assembleSmoke
```

The smoke package is `com.littleorbit.bigorbit.smoke`, visibly labeled **Big Orbit QA**, and targets only the isolated loopback smoke API. Validate package/version/label and absence of production signing metadata before installing it. Initial device enrollment requires a disposable administrator with current MFA; never use production recovery codes in screenshots or test logs. Revoke the smoke device and delete the disposable account after testing.

The context fetcher may be tested only with its fixed source keys. Cover redirects, loopback/private/link-local DNS, oversized bodies, wrong media types, timeouts, script/style removal, and instruction-shaped text. Do not add an arbitrary-URL debug endpoint.

## Partner notification development

The server stores account preferences and random app-installation UUIDs. Do not use hardware identifiers. Smooch and note-edit transactions create short-lived events and one pending delivery per active installation. The foreground socket carries only `notification.available`; clients must fetch the authorized event before displaying it. Acknowledge only after Android accepts the post, and test that another installation remains pending. On Android 13 and later, test runtime permission denial and recovery; on every supported API, test disabled channels, sign-out device disabling, process restart, the 15-minute fallback, and generic lock-screen public text. A local pass cannot establish OEM background timing on a physical phone.

## Our Space attachment development

The API writes uploads to the private `attachment-data` volume. `media-worker` streams pending bytes to the internal-only `clamav` service, then rebuilds images and PDFs or remuxes audio/video before marking them available. ClamAV can take about 90 seconds to download definitions and become healthy on its first start. Scanner or sanitizer failure leaves content unavailable.

Use synthetic files. Exercise JPEG/PNG/WebP/GIF, PDF, TXT/Markdown, MP3/M4A/Ogg, and MP4/WebM; unsupported extensions and misleading media types must fail. Cover a missing `Content-Length`, chunks above 4 MiB, gaps, replayed operation IDs with different metadata, an original hash mismatch, malware detection, scanner outage, metadata removal, the 100 MiB file limit, the 2 GiB couple quota, explicit delete, and expired-note cleanup. Android must verify the post-sanitization size and hash, preview from **Keep offline** without a network, and clear private copies after deletion or relationship state changes.

```powershell
docker compose --env-file .env -f infra/compose.yaml -f infra/compose.dev.yaml ps
docker compose --env-file .env -f infra/compose.yaml logs media-worker clamav
.\.venv313\Scripts\python.exe -m pytest services/api/tests/test_note_attachments.py
```

Do not paste filenames, attachment bytes, local cache paths, or relationship content into logs or bug reports.

## Android updater development

The phone requests `https://lil-orb.pax-kun.com/api/v1/releases/current` and accepts only the matching versioned API APK endpoint or a historical canonical GitHub release asset. Create `data/releases/` and copy a signed APK there using `little-orbit-{version}.apk`; Compose mounts that ignored directory read-only into the API. Test pure policy and restart behavior without a device:

```powershell
.\gradlew.bat :apps:android:domain:test :apps:android:mobile:testDebugUnitTest
```

End-to-end installation needs a signed older build on an emulator or test phone and a newer, already-published test release using the same signing certificate. Never weaken URL, hash, package, version, or certificate checks to make a local fake APK pass. A first install may require Android's **Install unknown apps** permission; the app requests it only after the person starts an update.

RC10 asks once whether optional metadata discovery should run, schedules checks about every six hours when enabled, and keeps required-floor checks active. Validate that the worker never creates a DownloadManager request, Later suppresses only the current process, and a running or paused transfer with no progress for five minutes becomes stalled.

## Phone-hosted Wear installer development

The Settings installer uses Wear OS wireless debugging directly from the phone. The phone and watch must be on the same trusted Wi-Fi network. On the watch, enable developer options, wireless debugging, and **Pair new device**, then enter the displayed six-digit code in the phone app. Android 13 and later may request nearby-device permission for DNS-SD discovery; manual host and ports remain available after denial. Android 17 local-network permission becomes relevant when the app targets SDK 37; RC10.1 compiles with SDK 37 but still targets SDK 36.

The phone downloads only the exact `wear_apk_url` from current release metadata. Before pairing it verifies size, SHA-256, package, version, required watch feature, and the pinned signer. After pairing it rejects phones, unsupported SDKs, and downgrades. A missing or pre-May-2026 watch patch level must show a user-overridable warning. Test the pure policy with:

```powershell
.\gradlew.bat :apps:android:mobile:testDebugUnitTest --tests "com.littleorbit.mobile.WearInstallPolicyTest"
```

Kadb 2.1.4 is isolated behind `KadbWatchClient` because its published Android bytecode targets Java 21 while Little Orbit production source stays Java 17. Android modules compile with SDK 37. The phone bundles Conscrypt 2.6.0 and excludes HiddenApiBypass so pairing uses a public TLS exporter API. Do not import Kadb types outside that adapter or increase either dependency without checking bytecode, compile-SDK metadata, native-library page alignment, license, and a physical pairing/install flow. Turn off wireless debugging on the watch after testing and use **Forget watch authorization** before handing a device to someone else.

When reproducing pairing failures, keep the watch's wireless-debug page visible and record only the named stage and safe `WPAIR`, `WCONN`, `WINFO`, or `WINST` code. Test continuous service updates, loss and port rotation, an authenticated first command, fresh pairing, remembered authorization, package-session commit, and manual entry. Kadb establishes connections lazily, so `connectionCheck()` cannot prove a newly created client is authorized. Never record the host, ports, pairing code, fingerprint, raw exception, or key material in committed logs.

## Smooch and proximity development

Use two disposable verified accounts for delivery tests. Cover the sixth send inside a rolling hour, exact hour expiry, duplicate operation IDs, a queued send older than 15 minutes, notification privacy, DST week boundaries, unpair archives, repairing isolation, and either account's deletion. Do not place message content in admin fixtures.

Location testing requires both the Android runtime permission and both accounts' in-app consent. Confirm the foreground-service notification remains visible, the first fix is requested promptly, WorkManager can queue while offline, and either consent or permission removal stops the service and clears local samples. Server acceptance proves only that a sample arrived; only two consecutive accurate, nearby matched pairs can establish estimated nearby time.

For 1.0.1, also test asymmetric two-minute and 15-minute streams. A second
strong nearby anchor may confirm at most a 20-minute gap when no intervening
observation reports apart or poor accuracy. The open gap remains uncounted, a
lone phone cannot extend the five-minute live lease, and a network transition
only triggers recovery. Verify that no SSID, BSSID, IP address, or network
fingerprint enters requests, logs, diagnostics, or storage. Collection-health
sharing is separately opted in per installation, is visible only to the active
partner, exposes no installation ID, and disappears after opt-out, unpair, or
24 hours.

Use `deduplicate-notes` without `--apply` before any duplicate cleanup. Applying
duplicate archival or retained-history reaggregation requires the checksum-valid
encrypted backup sidecar described in `BACKUP-RESTORE.md`; never supply a
fabricated or production-unrelated manifest. Test Our Space create-response
loss, repeated autosave, pause/back flushes, process death, a newer partner
revision, each explicit conflict choice, attachment reference rewriting, and
animated GIF pause/play with reduced motion enabled.

## Profile photo development

Use synthetic images only. The server accepts JPEG, PNG, and WebP up to 5 MiB, rejects animation and decompression bombs, removes source metadata, and emits 512-pixel plus 128-pixel WebP variants. Verify owner fetch, current-partner fetch, unpaired rejection, delete/re-add cache invalidation, account export, and Wear launcher synchronization. Never add profile image fixtures containing a real person.
