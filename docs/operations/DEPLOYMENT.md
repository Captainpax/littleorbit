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

## Signed Android releases

Keep the PKCS12 release store and its four `ANDROID_SIGNING_*` settings outside Git. Back them up separately because Android will reject an update signed by a replacement key. Increment `versionCode` before every published update, set the intended `versionName`, then build and verify both targets:

```powershell
.\infra\scripts\build-signed-android.ps1
```

The script loads signing values from the ignored `.env.android-signing`, which Compose never reads. It fails when any value or the store is missing, builds phone and Wear OS release APKs, verifies each signature with the newest installed Android `apksigner`, requires the same certificate on both, and writes APK, SHA-256 files, and `release-manifest.json` under `dist/android/`. The manifest reads the two version codes from separate Gradle outputs.

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

After publication, verify `/api/v1/releases/current`, both complete APK downloads, a 1,024-byte range from each, `/download`, `/patch-notes`, and `/patch-notes.xml`. On the phone, verify the automatic-check choice without starting a download, the persistent update banner, the visible location foreground service after mutual consent, immediate stop after opt-out, Smooch notification privacy, and the Wear installer's manual-address fallback. A phone-side installer smoke test does not close the physical-Wear gate.

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

Before publication, test an authorized synthetic image and PDF through reservation, chunk resume, clean scan, metadata removal, verified Android preview, keep-offline preview, deletion, and note-expiry cleanup. Reject an unauthorized note ID before attachment lookup, a conflicting idempotency replay, an oversized chunk, a wrong original digest, a quarantined file, and a download attempted before availability. Run both backup scripts after deployment and complete a disposable restore drill before treating attachments as production-ready.
