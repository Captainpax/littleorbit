# Home deployment runbook

Public availability depends on this computer, home power, internet service, router, and the Nginx Proxy Manager host remaining online. This topology is suitable for learning and a small service only after security, backup, and device release gates pass.

## Before touching live routing

1. Reserve `192.168.50.182` for this computer's network adapter in router DHCP and verify the lease after reconnect/reboot.
2. Copy `.env.example` to a protected `.env`, generate independent random secrets, configure production SMTP, and replace GitHub placeholders.
3. Run tests, build containers, migrate a fresh database, start the stack, and verify `http://192.168.50.182:8180/api/v1/health/ready` from the NPM host.
4. Restore the newest backup into an empty test database and perform a login smoke test.
5. Verify DNS for `lil-orb.pax-kun.com` without modifying unrelated records.

Promote the first owner only after that person has registered and verified their email:

```powershell
docker compose --env-file .env -f infra/compose.yaml exec api python -m little_orbit_api.cli promote-admin owner@example.com
```

Then visit `/admin/enroll`, re-enter the owner password, scan the TOTP QR code, confirm one current code, and store the one-time recovery codes. The command never creates an account or bypasses email verification.

## Windows Firewall

Create an inbound TCP rule for local port 8180 scoped to remote address `192.168.50.6`. Remove or disable any broader prior rule for the same application port. Verify another LAN host cannot connect while NPM can. Record the actual rule name in private operations notes.

From an elevated PowerShell prompt, apply the repository's idempotent rule:

```powershell
.\infra\scripts\configure-windows-firewall.ps1
```

Use `-WhatIf` to preview the named rule. The script creates or updates only `Little Orbit Gateway - NPM only` and leaves unrelated rules unchanged.

## Nginx Proxy Manager

Create one proxy host for `lil-orb.pax-kun.com`:

- Scheme: HTTP
- Forward hostname/IP: `192.168.50.182`
- Forward port: `8180`
- WebSocket support: enabled
- Block common exploits: enabled
- Certificate: Let's Encrypt for the exact hostname
- Force SSL and HTTP/2: enabled after certificate issuance succeeds

Keep `REGISTRATION_OPEN=false` while Mailpit is the configured SMTP service. Open registration only after an external SMTP delivery test confirms that verification and password-reset links use the public HTTPS origin.

Test website pages, `/patch-notes`, `/patch-notes.xml`, `/.well-known/assetlinks.json`, `/api/v1/health/ready`, a real WebSocket upgrade, signup email delivery, and certificate renewal/recovery. Enable HSTS only after those checks and a rollback path succeed. The initial live NPM change is an explicit deployment action; screenshots or a saved draft are not proof that traffic works.

## Restart recovery

Set Docker Desktop/engine and the Compose stack to start after host reboot. Reboot the host, then verify DHCP address, firewall scope, all health checks, public HTTPS, WSS, email, worker schedules, and one curated fallback pool while Ollama is stopped.

The internal `gateway-api` link reserves `172.30.14.2` for Caddy and `172.30.14.3` for FastAPI. Keep both assignments together with `TRUSTED_PROXY_IP`; this prevents a recreated API container from dynamically taking the trusted proxy address before Caddy starts. After a Compose recreation, inspect the resolved configuration and confirm both containers are healthy before testing forwarded-client throttles.

## Signed Android releases

Keep the PKCS12 release store and its four `ANDROID_SIGNING_*` settings outside Git. Back them up separately because Android will reject an update signed by a replacement key. Increment `versionCode` before every published update, set the intended `versionName`, then build and verify both targets:

```powershell
.\infra\scripts\build-signed-android.ps1
```

The script loads signing values from the ignored `.env.android-signing`, which Compose never reads. It fails when any value or the store is missing, builds phone and Wear OS release APKs, verifies each signature with the newest installed Android `apksigner`, requires the same certificate on both, and writes APK, SHA-256 files, and `release-manifest.json` under `dist/android/`. The manifest reads the two version codes from separate Gradle outputs. For a phone-only correction, `-ReuseWearApk data/releases/<prior-wear>.apk` builds only the phone and verifies the unchanged Wear package, version code, hash, and signer before placing the same bytes in the new manifest. Release notes must identify that reuse explicitly.

Publish in this order:

1. Build, hash, and verify both APKs locally.
2. Commit the final release code and documentation. Create the immutable GitHub tag and upload the exact APK/checksum files as a recovery mirror.
3. Update the verified fallback in `apps/web/src/lib/release.ts` from the generated manifest, then deploy the API and rebuilt web image. Compose mounts release storage read-only.
4. Stage the exact artifacts. This rechecks file hashes, both APK manifests, and both signers before copying into the ignored `data/releases` directory:

```powershell
.\infra\scripts\publish-signed-android.ps1 `
  -ManifestPath dist/android/release-manifest.json
```

1. Put the public release-note text in a temporary UTF-8 file, then publish from the same manifest. `-Publish` is the explicit immutable step; do not type artifact values by hand:

```powershell
.\infra\scripts\publish-signed-android.ps1 `
  -ManifestPath dist/android/release-manifest.json `
  -ReleaseNotesPath release-notes.txt `
  -Publish
```

Add `-RequiredAfter` only for a separately verified compatibility-floor rollout.
Verify both a complete response and a resumed slice through the public proxy. The range request must return `206`, `Content-Range: bytes 0-1023/15823790`, and exactly 1,024 bytes:

```powershell
curl.exe -fSI https://lil-orb.pax-kun.com/api/v1/releases/1.0.0-rc.6/apk
curl.exe -fsS -H "Range: bytes=0-1023" -D - -o range-check.bin https://lil-orb.pax-kun.com/api/v1/releases/1.0.0-rc.6/apk
curl.exe -fSI https://lil-orb.pax-kun.com/api/v1/releases/1.0.0-rc.6/wear-apk
```

Omit `--required-after` for normal optional releases. RC6 moved the floor to version code 6 at `2026-09-12T17:45:00Z`, after the deployed migration, both hosted artifacts, updater discovery, complete/range downloads, and health checks passed. Once a published record exists, corrections require a new version and new tag; the API deliberately rejects edits and unpublishing. RC7 demonstrates that rule: a Wear layout correction received version code 7 while the active minimum remains 6.

The public certificate and expected fingerprint are documented in [`../signing/README.md`](../signing/README.md).

## RC8 profile and Wear checks

Migration `0011` stores normalized profile-photo variants in PostgreSQL. Before serving RC8, confirm the gateway request-body limit is 6 MiB, the API accepts at most 5 MiB, the database backup includes `account_profile_photos`, and admin routes still expose no image bytes or relationship content.

The website no longer distributes a PowerShell watch installer. `/app/install-wear` is an Android App Link into the phone installer, and `/.well-known/assetlinks.json` pins the same release certificate used by both APKs. Keep the raw Wear APK endpoint for advanced recovery. Validate the installer on a physical phone/watch pair before calling it release-ready: discovery grant and denial, manual address fallback, first pairing, remembered authorization, old-patch warning, upgrade, current-version result, downgrade rejection, wrong-device rejection, and **Forget watch authorization**.

RC8 artifacts use phone version code 8 and Wear version code 8. Phone size is 23,277,980 bytes with SHA-256 `a20947a885959f0201f7559052b272fcd1a7d4f3f6057029d49521627270d156`; Wear size is 14,130,618 bytes with SHA-256 `de1b1e5af6b983b412e89e46702396bd5db027a0a689697c5f28d577b5ef723c`. The compatibility floor remains version code 6 and RC8 has no enforcement time.

## RC9 corrective release

RC9 moves home-widget database reads and rendering from broadcast-receiver callbacks into unique WorkManager jobs, adds a fixed quiz-reveal exit, and replaces the removed library crop activity with an internal inset-safe crop screen. Confirm the merged release manifest contains only the non-exported `ProfileCropActivity` and no exported `com.canhub.cropper.CropImageActivity` before publication.

RC9 artifacts use phone version code 9 and Wear version code 9. Phone size is 23,285,988 bytes with SHA-256 `28cdcbc6cd58b26507979e77562de6123e15628766b605108e1c98c26da016b3`; Wear size is 14,130,618 bytes with SHA-256 `e51241347840273667956e60dc36c560ef2e9b4dab2b57f7f89374dfae4c4036`. The compatibility floor remains version code 6 and RC9 has no enforcement time.

## RC10 data and client release

Take a PostgreSQL backup before migration `0012`. After upgrade, verify the new Smooch, note-metadata-operation, note archive, and couple-home-timezone structures; run account-deletion cleanup in a transaction-safe test before enabling public Smooch traffic. The API must still exclude note and Smooch content from owner-console routes.

The worker depends on a healthy API as well as PostgreSQL and model initialization. The API health gate runs only after its Alembic entrypoint finishes, preventing scheduled maintenance from querying RC10 columns during the migration window. After a deployment, inspect both API and worker logs and restart the worker if an older Compose revision allowed it to race migration.

RC10 uses phone version code 10. Its published Wear metadata says version code 10, but the immutable 14,130,626-byte Wear APK with SHA-256 `22f629a96b7a513ca9162a6fcff0b7e7dfdd42558b9c1ddce0cd1c0594934f8e` contains version code 9. The strict phone verifier rejects that mismatch. Do not alter the RC10 record or bytes; deploy RC10.1 as a new correction. The phone APK remains 23,389,918 bytes with SHA-256 `e6039a5397e1675e8d7548a6a65ede07096cc84f7a5fd82a2887a48c59220104`. The compatibility floor remains version code 6 and RC10 has no enforcement time.

After publication, verify `/api/v1/releases/current`, both complete APK downloads, a 1,024-byte range from each, `/download`, `/patch-notes`, and `/patch-notes.xml`. On the phone, verify the automatic-check choice without starting a download, the App updates banner, the visible location foreground service after mutual consent, immediate stop after opt-out, Smooch notification privacy, and the Wear installer's manual-address fallback. A phone-side installer smoke test does not close the physical-Wear gate.

## RC10.1 Wear correction

Build with `infra/scripts/build-signed-android.ps1` and publish every artifact field from
the generated `release-manifest.json`. Independently inspect the phone and Wear APK
manifests before copying bytes to release storage. RC10.1 must contain phone version
code 11 and Wear version code 10, use the existing signing certificate, pass 16 KiB
zip alignment, and contain no HiddenApiBypass classes. The compatibility floor stays at
6 and the corrective release has no enforcement time.

After the public record is immutable, use the strict signed phone build to upgrade the
physical watch from the actual RC10 Wear version code 9 to RC10.1 code 10. Confirm fresh
pairing, remembered reconnect without a new code, package-session completion, launcher
start, and a second current-version inspection. Never place local addresses, ports,
pairing codes, fingerprints, or raw transport errors in release evidence.

## RC11 Our Space and Smooch release

Take a PostgreSQL backup before migration `0013`. The deployment adds the private `attachment-data` and `clamav-data` volumes, a one-shot `attachment-init`, `media-worker`, and internal-only `clamav` service. The init container assigns a fresh attachment volume to the unprivileged application user before the API starts. No attachment service publishes a host port. Wait for ClamAV health and current signatures, API migration head, worker/media-worker startup, and gateway health before accepting uploads. Confirm the owner console reports attachment queue counts without filenames or content.

Build RC11 with phone version code 12 and Wear version code 11 from `infra/scripts/build-signed-android.ps1`. Publish only the generated sizes, hashes, manifest version codes, and existing signing-certificate digest. Keep compatibility-floor enforcement unchanged unless a separate reviewed incident requires it.

RC11.1 corrects the updater action layout with phone version code 13 and Wear version code 12. Its API release notes must stay concise enough for older clients whose release-note body is not scrollable; keep the full immutable explanation in `docs/releases/1.0.0-rc.11.1.md` and the GitHub release.

RC11.2 corrects package-session ordering with phone version code 14 and Wear version code 13. Close and sync every `PackageInstaller.Session` output stream before calling `commit`; an open stream causes Android to abandon the session before it can show the system installer.

RC10.1 and RC11.1 execute their old, broken installer code even when downloading a newer APK, so they require one manual update to RC11.2 or later. RC11.3 has phone version code 15 and Wear version code 14 and exists to test an installed RC11.2 client through the repaired update path. Do not describe the boundary as repaired until that in-place update reaches Android confirmation and installs successfully.

## RC12 shell, activity, and attachment release

Take a PostgreSQL backup before migration `0014`. After upgrade, verify the couple-scoped activity event and seen-watermark tables, the 30-day worker purge, and immediate feed removal on unpairing. The owner console must expose neither event rows nor their target titles. Build RC12 with phone version code 16 and Wear version code 15, and keep compatibility-floor enforcement unchanged.

Before publication, run the isolated paired-account stack and transparent PNG/GIF pipeline, then run the Android smoke build on API 29, API 30, API 36 phone, and a wide API 36 tablet. Confirm the wide navigation is static and its content remains tappable, the right panel opens programmatically without stealing the back edge, the Markdown dock sits above the keyboard, and an authorized sanitized image renders after digest verification. Launch the Wear artifact on a round API 34 emulator and confirm the stale fallback. These emulator checks do not close the physical two-phone or physical phone/watch release gates.

## RC12.1 notification and preview release

Take paired PostgreSQL and attachment backups before migration `0015`. After upgrade, verify preference, random-installation, short-lived event, and per-device delivery tables. Run `infra/scripts/notification-smoke.py` against the isolated stack before production publication. Confirm one acknowledgement does not consume another installation's delivery, a new acknowledgement suppresses the legacy account-wide Smooch queue, note-edit cooldown works, and active partner presence suppresses the alert. The WSS message itself must contain only `notification.available`.

Build RC12.1 with phone version code 17. The Wear code remains 15 and the RC12 Wear APK is reused byte-for-byte because there is no Wear change. Deploy one API process while the foreground hint hub is in memory; durable polling still prevents event loss if a hint is missed. Verify migration head `0015`, worker cleanup, API/gateway health, public release metadata, complete and range downloads, patch notes, RSS, and that no new host port exists. The emulator matrix does not close notification timing, lock-screen, process-kill, or multi-phone physical gates.

## RC13 countdown, quiz, and avatar release

Take PostgreSQL and attachment backups before migration `0016`. The migration adds timed/all-day countdown fields, private reminder rows, relationship-scoped partner-assigned avatars, and the expanded notification kind constraint. It deliberately deletes old account-owned profile-photo rows; announce that one-time reset before deployment and do not attempt to reinterpret a self-selected image as partner-assigned. Rehearse `0016 -> 0015 -> 0016` with RC13 event rows present, because downgrade must remove notification kinds that the older constraint cannot represent.

Run the isolated RC13 integration smoke before publication. Verify atomic countdown create/reschedule alerts, reminder privacy between both members, self-photo endpoint retirement, partner-avatar assignment, self-assignment rejection, unpair/account cleanup, malformed timing combinations, invalid timezones, and unrelated event delivery when the daily quiz pool is unavailable. Check migration head `0016`, one API process, worker cleanup, API/gateway health, and the absence of new host ports.

Build RC13 with phone version code 18. Reuse the exact RC12.1 Wear code 15 APK because Wear source behavior is unchanged; record its independent version, byte count, hash, and certificate instead of inferring them from the phone build. Exercise paired smoke accounts on phone API 29, API 30, API 36, the wide API 36 tablet, and the round API 34 Wear emulator. Confirm the API 29 countdown route, expanded editor height, all-day 9:00 AM reminder calculation, reboot/timezone reconciliation, one-way calendar intent, responsive weighted quiz choices, partner-only avatar controls, and generic notification public versions.

After publication, verify `/api/v1/releases/current`, complete and ranged phone/Wear downloads, `/download`, `/patch-notes`, `/patch-notes.xml`, `/showcase`, and the exact generated release manifest hashes. A device/emulator check cannot close the two-physical-phone alert timing, actual calendar provider, OEM alarm/battery, or phone-to-watch transfer gates.

Before publication, test an authorized synthetic image and PDF through reservation, chunk resume, clean scan, metadata removal, verified Android preview, keep-offline preview, deletion, and note-expiry cleanup. Reject an unauthorized note ID before attachment lookup, a conflicting idempotency replay, an oversized chunk, a wrong original digest, a quarantined file, and a download attempted before availability. Run both backup scripts after deployment and complete a disposable restore drill before treating attachments as production-ready.

## RC14 API security migration

Take a PostgreSQL backup before migration `0017`. The migration adds privacy-minimized throttle buckets and separate pending administrator-MFA fields; it does not replace an enabled factor. Upgrade the API and worker to the same revision, wait for Alembic head and health, and confirm the worker removes inactive throttle rows. Do not run `test_security_rc14_postgres.py` against this database because that isolated test suite truncates all application tables.

Before serving RC14 traffic, verify configured limits with synthetic accounts and confirm no raw IP, email, token, password, TOTP, recovery code, or pair code appears in the throttle table or security events. Exercise a successful reset with two outstanding links, an old-session rotation attempt, deleted-account login, pair redemption expiry/reuse and competing confirmations, and a one-sided legacy quiz export. Replace an enrolled test administrator factor using current proof; confirm the old factor remains valid until the new factor is confirmed, every earlier session is then revoked, recovery codes remain one-use, and the configuration response contains only the documented allowlist.

Open note and notification sockets with disposable sessions, then revoke each session while the socket is active and while it is idle. Both paths must close within the 30-second revalidation bound, and a queued note operation after revocation must not commit. These checks establish server behavior only; the two-physical-phone notification and full phone/watch release gates remain open.

Raw-location ingestion schedules expiry five minutes before `recorded_at + 24 hours`. After deploying the API and worker, run one maintenance cycle and use privacy-safe aggregate queries to prove that no `location_samples` row is past either `expires_at` or `recorded_at + 24 hours`. Repeat after at least one normal five-minute worker interval. Backups must continue excluding all `location_samples` rows.

## RC15 self-hosted notification correction

Take an encrypted PostgreSQL backup before migration `0024`. Rehearse `0023 -> 0024 -> 0023 -> 0024` on the isolated stack and confirm that the seven retired provider-address and delivery-attempt columns plus their partial index are absent at head. The migration preserves random installations, short-lived events, per-installation delivery rows, preferences, and acknowledgements.

Build phone version code 20 as `1.0.0-rc.15`. Reuse the exact RC14 Wear version code 16 APK because Wear behavior is unchanged; record that byte identity in the release notes. Before publication, inspect the phone dependency tree, merged manifest, APK contents, server dependencies, Compose configuration, and container environment for hosted notification SDKs, credentials, addresses, or egress paths. An RC14 heartbeat may include only the compatibility value `push_token: null`; reject every non-null value and always return `push_enabled: false`.

Verify an authenticated foreground WSS hint, two independent installation fetches and acknowledgements, offline recovery, permission denial and recovery, process restart, and eventual WorkManager polling. Do not describe background delivery as instant: Android Doze and manufacturer battery controls can delay a nominal 15-minute check. Confirm that upgrading an RC14 phone deletes every retired local hosted-transport key before publishing RC15.

## RC16 stale-session correction

Build phone version code 21 as `1.0.0-rc.16` and reuse the exact RC14 Wear version code 16 APK. Before publication, use an isolated paired account to populate Home and Our Space, revoke only that disposable phone session, cold-launch the app, and confirm it shows the signed-out Home rather than cached avatars with a false “Not connected” pairing state. Verify the encrypted session key and profile thumbnails are gone, private work is cancelled, no crash occurs, and signing in again restores the existing server-side couple and shared-note directory. A production couple row that still has exactly two active verified members must not be edited to repair this client state. On a valid paired session, verify the Home setup card disappears after all four core steps resolve ready and that Pairing & relationship shows the confirmed unpair action. Do not execute that destructive relationship test against a real couple; use a disposable paired account and confirm both archives plus passive-surface purging.

## RC17 document and nearby-time correction

Before deployment, record only privacy-safe production aggregates: active-note counts and exact-equality groups without content, and per-member consent/sample counts without coordinates. Never use administrator tooling to inspect the affected note text or precise locations. The API's five-minute exact-document recovery runs after current-couple authorization and locking; verify it against disposable PostgreSQL with two different create IDs and confirm one stored, partner-visible note.

Build phone version code 22 and Wear version code 17 as `1.0.0-rc.17`. Verify both independent APK manifests, sizes, hashes, and the pinned signer. Deploy API, worker, web, and gateway from the same commit, publish the immutable record, then verify complete and ranged downloads, update discovery, patch notes/RSS, and local/public health. An existing exact revision-zero duplicate may be archived only after a scoped backup and aggregate proof that the retained row has the revision history; never select or print its title or body during cleanup.

After both partners update, open Little Orbit once on each phone so RC17 can reconcile foreground/background permission with both server consent states. The first interval requires two confident paired observations. Check that the server freshness time follows the older newest member sample, that a stopped phone makes the display stale, and that phone/widget/Wear surfaces show nearby duration without pairing age. Missing historical evidence cannot be reconstructed.

## 1.0 chronological together-time release

Take an encrypted PostgreSQL backup and attachment metadata backup before migration `0025`. Confirm the database dump excludes `location_samples`; raw coordinates must never enter backup output. Rehearse a clean upgrade to head on an explicitly disposable PostgreSQL database and run the together-time concurrency and retention suites only with `LITTLE_ORBIT_TEST_DATABASE_URL` pointing to that database. Migration `0025` records daily estimate provenance and does not reinterpret old coordinate-free totals.

Deploy API, worker, web, media worker, and gateway from one commit. Wait for Alembic head `0025`, healthy API and gateway, worker startup, and the ordinary raw-location maintenance interval. Legacy v1/v2 together-time routes must return structured `410 Gone`; `/api/v3/together-time` and relationship-scoped `/api/v3/together-time/location-batches` remain behind normal session and exact-couple authorization.

Build phone code 23 and Wear code 18 as `1.0.0` with `infra/scripts/build-signed-android.ps1`. Analyze both APKs independently, verify the pinned signing certificate, and publish only the generated size, hash, package, and version metadata. The Android Room 4-to-5 migration intentionally deletes pending legacy location rows because they lack a relationship identity; document this privacy boundary and verify a post-upgrade collection creates a newly scoped row.

Publish with a future `required_after` instant long enough to verify an installed RC17 client's metadata check, explicit download, byte count, hash, certificate, Android confirmation, and in-place replacement before the version floor activates. Then verify current metadata, complete and 1,024-byte ranged phone/Wear downloads, patch notes, RSS, `/status`, and local and public health. Once the floor is active, phone versions below code 23 must receive `426 client_upgrade_required` on protected versioned routes while public release metadata and APK bytes remain reachable.

For together-time, use disposable paired accounts or privacy-safe aggregates only. Verify unequal phone cadence, a nearby-apart-nearby sequence, a lone-phone stale transition, queue retry after temporary throttling, exact duplicate acceptance, conflicting sample rejection, correction preservation, process restart, and raw-coordinate expiry. On Android, keep the detail screen open: observed seconds may project only through the server deadline using elapsed realtime, then must freeze. Widget and Wear must show the authoritative observed value and stale state rather than continuing the projection. A synthetic/emulator pass does not establish real-world physical proximity; record that gate separately.

## 1.0.1 Together Time and Our Space reliability

Phone 1.0.1 uses version code 24. Reuse the exact signed 1.0.0 Wear code 18 APK with `-ReuseWearApk`; the generated manifest must independently prove the same Wear bytes, hash, package, code, and signer. The owner explicitly waived the unavailable physical tablet soak on 2026-09-19. Preserve that missing evidence in the verification report, publish only after the signed phone manifest and production health checks pass, and keep the compatibility floor at code 23 during the optional rollout.

Use this order against an explicitly identified target. The duplicate command prints counts only and never titles or bodies. `--apply` refuses to run unless the supplied sidecar names a checksum-valid encrypted dump that excluded raw locations and device-health snapshots.

```powershell
# 1. New image against the existing schema: classification only.
docker compose --env-file .env -f infra/compose.yaml run --rm api `
  python -m little_orbit_api.cli deduplicate-notes

# 2. Stop mutation services at one consistency point and create the coordinated age backup.
powershell -File infra/scripts/backup-all.ps1

# 3. Rehearse migration 0026 on disposable PostgreSQL, then migrate production API-first.
docker compose --env-file .env -f infra/compose.yaml run --rm migrate

# 4. Repartition retained coordinate-free buckets and recompute only retained raw evidence.
docker compose --env-file .env -f infra/compose.yaml run --rm `
  -v "${PWD}/backups:/backups:ro" api `
  python -m little_orbit_api.cli reaggregate-together-time --apply `
  --backup-manifest /backups/postgres/<verified>.dump.age.json

# 5. Reversibly archive only safe exact untouched duplicates for the normal seven-day window.
docker compose --env-file .env -f infra/compose.yaml run --rm `
  -v "${PWD}/backups:/backups:ro" api `
  python -m little_orbit_api.cli deduplicate-notes --apply `
  --backup-manifest /backups/postgres/<verified>.dump.age.json
```

The read-only bind intentionally exposes only the backup directory to the one-shot command. Verify the selected sidecar before use; the examples do not authorize guessing it. Re-run the classifier after archival and require `safe_to_archive: 0`. Ambiguous groups remain untouched for manual review. Check that corrections retain their revisions across local-time reaggregation, that raw coordinates still expire before 24 hours, and that opted-in health rows expire at 24 hours and are absent after unpair.

Before publication, test exactly-20-minute and longer gaps, intervening apart/poor readings, 2-minute/15-minute streams, reordered retries, one-phone-only collection, 23/25-hour days, and opt-in/out authorization. Exercise note create response loss, rotation, process death, continuous typing, a newer partner revision, attachment-safe fork, GIF pause/play and reduced motion. The final gate requires a physical phone/tablet soak through screen-off, Wi-Fi/cellular transition, temporary offline state, battery restriction, and a forced 15-minute gap followed by a confirming anchor.
