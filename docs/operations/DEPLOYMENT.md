# Home deployment runbook

After cutover, public availability will depend on Unraid, home power, internet service, the router, and the separate Nginx Proxy Manager host remaining online. This topology is suitable for learning and a small service only after security, backup, and device release gates pass. The target production host is Unraid at `192.168.50.14`; Nginx Proxy Manager remains at `192.168.50.6` and public DNS/TLS remain unchanged.

## Unraid production layout

Use these non-exported paths. Do not place the live database or attachments beneath a generic appdata/user-share path that Unraid mover or snapshot tooling can relocate while the service runs. This follows Unraid's separation of [container working data and shares](https://docs.unraid.net/unraid-os/using-unraid-to/manage-storage/shares/).

| Host path | Purpose | Required boundary |
|---|---|---|
| `/mnt/cache/little-orbit-live/` | PostgreSQL, attachments, immutable releases, Ollama, and ClamAV state | Cache-only direct pool path; PostgreSQL `999:70` mode `0700`, attachments `65532:65532`, release bytes read-only in application containers |
| `/mnt/cache/little-orbit-deploy/` | Clean source checkout and fixed launcher | Non-exported; no runtime secrets or signer plaintext |
| `/mnt/cache/little-orbit-secrets/` | Root-only runtime environment and backup age identity | Mode `0700`; never commit, print, or mount into unrelated containers |
| `/mnt/cache/gpu-coordinator/` | Stable `gpu.lock` inode and content-free diagnostics | Shared GID, sticky/setgid directory `3770`, root-owned single-link lock `0660`; never replace the inode during metadata updates |
| `/mnt/cache/little-orbit-tools/` | Checksum-pinned host-only tools such as `age` | Non-exported cache-only share; never add it to production container mounts |
| `/mnt/cache/vault/little-orbit/android-signing/` | Separately encrypted Little Orbit and Big Orbit signer bundles | Outside production Compose; decrypt only into tmpfs for one-shot signing |
| `/mnt/user/little-orbit-backups/` | Encrypted, privacy-filtered database/attachment pairs | Array-only share; local recovery, not off-host disaster recovery |

Run `infra/scripts/unraid-bootstrap.sh` as root on the verified `.14` host to create the layout and install the checksum-pinned `age` binary. The script refuses another host and refuses to create state unless `/mnt/cache` is the expected BTRFS device mount and `/mnt/user` is the exact `shfs` mount; mere root-filesystem directories do not pass. It requires SMB and NFS export to be disabled, may add the two missing NFS-disable keys to an otherwise exact legacy share configuration, and rejects partial or conflicting NFS policy. After validating each persistent share file, it applies the same fixed storage policy through Unraid's local management command so the running `shfs` sees it before any directory or file is created. It then writes a root-owned mode-`0600` content-free `.array-placement` sentinel through `/mnt/user/little-orbit-backups/` so an empty backup share materializes on an array disk and can pass the physical-placement audit. Do not remove that sentinel. Exclude the live PostgreSQL and attachment directories from generic appdata backup/snapshot jobs.

Keep the root-only runtime environment at `/mnt/cache/little-orbit-secrets/runtime.env`. In addition to normal production secrets, it must resolve these deployment values:

```dotenv
PUBLIC_BASE_URL=https://lil-orb.pax-kun.com
GATEWAY_BIND_ADDRESS=192.168.50.14
GATEWAY_INTERNAL_SUBNET=10.253.14.0/28
GATEWAY_CADDY_IP=10.253.14.2
GATEWAY_API_IP=10.253.14.3
TRUSTED_PROXY_IP=10.253.14.2
LITTLE_ORBIT_DATA_ROOT=/mnt/cache/little-orbit-live
LITTLE_ORBIT_BACKUP_ROOT=/mnt/user/little-orbit-backups
RELEASE_STORAGE_ROOT=/mnt/cache/little-orbit-live/releases
GPU_COORDINATOR_ROOT=/mnt/cache/gpu-coordinator
GPU_LOCK_HOST_PATH=/mnt/cache/gpu-coordinator/gpu.lock
GPU_COORDINATOR_GID=2000
AI_SCHEDULE_TIMEZONE=America/Los_Angeles
AI_LEARNING_LOCAL_HOUR=1
AI_GENERATION_LOCAL_HOUR=3
AI_WORK_RETRY_HOURS=6
AI_WORK_MAX_RUNTIME_SECONDS=6600
AI_COVERAGE_DAYS=14
```

Do not choose `172.30.14.0/28`: the target's Pterodactyl bridge owns `172.30.0.0/16`. Verify `10.253.14.0/28` is still unused before every first deployment on a rebuilt host.

The launcher always applies Compose in this order:

```bash
bash /mnt/cache/little-orbit-deploy/repo/infra/scripts/unraid-stack.sh validate
bash /mnt/cache/little-orbit-deploy/repo/infra/scripts/unraid-user-script.sh startup
```

The quiet validation resolves `compose.yaml`, then `compose.gpu.yaml`, then `compose.unraid.yaml` without printing expanded environment values. Production starts always go through the fail-closed dispatcher so the firewall is installed before publication and the gateway is stopped after any boundary failure. Under the [Docker Compose merge rules](https://docs.docker.com/reference/compose-file/merge/), relative paths still resolve from the base Compose project while target-keyed volume mounts in the Unraid override replace their base counterparts. The launcher discards ambient overrides for every fixed production setting and validates the effective port model; the post-start firewall check also verifies the running Docker bindings. Never print the rendered Compose model because it contains expanded secrets. Require that only `192.168.50.14:8180` is published. PostgreSQL, API, web, Ollama, ClamAV, media, mail, and context-fetcher ports must remain private.

## Unraid startup, firewall, and schedules

Before installing the schedules, set Unraid's host timezone to `America/Los_Angeles` in **Settings > Date and Time**.
The installer requires both `/boot/config/ident.cfg` to name that exact IANA timezone and the effective
`/etc/localtime` bytes to match its installed zoneinfo file. It fails before changing User Scripts if either check is
unavailable or mismatched; setting only a process `TZ` variable is not sufficient. Verify and install after the array
and Docker are available:

```bash
source /mnt/cache/little-orbit-deploy/repo/infra/scripts/unraid-timezone.sh
require_unraid_pacific_timezone
bash /mnt/cache/little-orbit-deploy/repo/infra/scripts/unraid-install-user-scripts.sh install
```

The default `install` mode writes the fixed wrappers but keeps startup and every cron entry disabled. This is the only
mode allowed before traffic has moved. After successful cutover validation, activate the already inspected entries
explicitly:

```bash
bash /mnt/cache/little-orbit-deploy/repo/infra/scripts/unraid-install-user-scripts.sh activate-after-cutover
```

Do not activate `.14` while `.182` schedules are enabled or before `.14` is the authoritative writer.

Each installed entry calls the fixed dispatcher rather than reconstructing a Compose command:

```bash
bash /mnt/cache/little-orbit-deploy/repo/infra/scripts/unraid-user-script.sh startup
bash /mnt/cache/little-orbit-deploy/repo/infra/scripts/unraid-user-script.sh pending
bash /mnt/cache/little-orbit-deploy/repo/infra/scripts/unraid-user-script.sh backup
bash /mnt/cache/little-orbit-deploy/repo/infra/scripts/unraid-user-script.sh test_restore
```

- `startup`: after array/Docker startup; verifies the exact mounts, applies the firewall, creates/validates paths, starts the exact stack, and rechecks the firewall/IPv6 boundary. A failed start or post-start check stops the gateway.
- `pending`: every five minutes; runs allowlisted Big Orbit operations. A concurrent runner may return successful `already_running` only for this mode.
- `backup`: daily at 08:00 `America/Los_Angeles`; a lock collision waits up to five minutes and then fails nonzero.
- `test_restore`: Tuesday at 07:00 `America/Los_Angeles`; it uses the same bounded lock behavior.

The dispatcher repeats the timezone check before every scheduled `backup` or `test_restore`, so later host drift fails
that run nonzero instead of silently executing Pacific wall-clock protection jobs at the wrong local time. The
five-minute `pending` runner remains interval-based, and queued typed operations are not reinterpreted as wall-clock
schedules.

The idempotent firewall script owns only its alternating `LITTLE_ORBIT_GATEWAY_A` and `LITTLE_ORBIT_GATEWAY_B` chains. It fully prepares the inactive chain before inserting it at the front of `DOCKER-USER`, then retires the previous chain, so a failed refresh remains fail-closed. It uses conntrack original-destination matching to accept source `192.168.50.6` for original target `192.168.50.14:8180`, rejects every other source for that destination, and returns unrelated traffic to the existing `DOCKER-USER` rules. It never flushes DMS or other rules. Startup fails if an IPv6 listener exposes port 8180. From `.6`, validate readiness with the real public host header; from another LAN peer, verify the direct request is rejected:

```bash
curl --fail -H 'Host: lil-orb.pax-kun.com' \
  http://192.168.50.14:8180/api/v1/health/ready
```

## Migration preflight

Do not change live routing until every item is recorded in a new verification entry:

1. Confirm no BTRFS operation is active, the array is started, parity is valid, and cache/array free space covers the database, attachments, immutable releases, rebuilt model/cache data, and backup retention.
2. Confirm `.14` has the intended static reservation, pin the SSH port 23 host key, install a temporary migration public key, and test batch authentication without weakening password policy.
3. Confirm Docker Compose and NVIDIA runtime versions, port 8180 availability, `10.253.14.0/28` availability, and absence of an IPv6 listener.
4. Build and migrate an isolated project with synthetic state; pre-pull the pinned Ollama models and refresh ClamAV. Do not copy Ollama or ClamAV caches from `.182`.
5. Deploy and verify Scriptarr's lock-aware Oracle and Raven behavior before Little Orbit can use the shared GPU. No new consumer may start while an Ollama, LocalAI, or NVENC process still owns VRAM, even when the advisory lock was released by a crash.
6. Confirm both Little Orbit users are off the app. Disable `.182` schedules, create a normal privacy-filtered encrypted backup, and pass a restore drill.
7. Record the source commit and image digests, migration head `0031`, privacy-safe table counts including the existing feedback and feedback-operation counts, attachment aggregate digest, and every immutable-release size/hash. Stage `.182` with code that understands migration `0032` before freezing it.

The worker deliberately does not depend on model installation: safe fourteen-day coverage must start even when the registry or Ollama is unavailable. Pre-pull and verify the two pinned model digests explicitly before enabling GPU work:

```bash
bash /mnt/cache/little-orbit-deploy/repo/infra/scripts/unraid-stack.sh \
  --profile model-setup run --rm model-init
```

## Application-cold exact transfer

The ordinary backup intentionally omits sensitive short-lived tables, so it is not the migration source. The migration command stops gateway, API, worker, media worker, and context fetcher, then refuses to continue while an `ai_runs` claim or Big Orbit AI request remains `running`. It streams a complete logical database directly through pinned SSH into an empty target. Frozen attachments and immutable releases land in sibling directories under `/mnt/cache/little-orbit-live`; only complete verified directory trees are renamed over the empty live paths. It has no archive-output option and must not be wrapped in redirection or `tee`.

Run from the clean `.182` checkout with exact paths to the temporary SSH identity and a one-host `known_hosts` file:

```powershell
python infra/scripts/direct_migration.py `
  --direction forward `
  --local-host 192.168.50.182 `
  --unraid-host 192.168.50.14 `
  --unraid-port 23 `
  --ssh-identity C:\protected\little-orbit-migration-ed25519 `
  --known-hosts C:\protected\little-orbit-migration-known-hosts `
  --backup-identity "$env:LOCALAPPDATA\LittleOrbit\backup-age-identity.txt" `
  --local-env .env `
  --local-release-root data/releases `
  --confirm forward-.182-to-.14-users-offline
```

The command first proves that target attachment and release storage are empty. It then streams the runtime environment plus fixed target-only path values—including the exact `/mnt/cache/gpu-coordinator/gpu.lock` bind—and the backup identity into root-only files; an existing file is accepted only when its bytes already match and is never overwritten. Before freezing `.182`, it builds every target-local application and migration image needed by the transfer or later startup without starting target writers. It starts only target PostgreSQL, requires every public target table to be empty, and only then freezes the source. Before promotion it compares source and destination inventories containing every public base-table count and Alembic head, normalized role attributes/memberships, database/schema/object/default ACLs, attachment file count/total bytes/aggregate digest without exposing paths, and every immutable release path/size/hash. A static least-privilege gate rejects extra role membership or grants; forward migration permits only the reviewed empty `ai_work_queue` table and its fixed API/worker/backup privileges. Its final JSON contains both inventories as cutover evidence. On success, the source writers deliberately remain stopped. Then:

1. Run the target migration container and require Alembic head `0032`.
2. Validate database roles/grants, exact pre/post counts, attachment aggregate digest, and immutable release sizes/hashes without inspecting content.
3. Apply and inspect the firewall while the target gateway is still stopped. The Unraid overlay uses an `on-failure` policy rather than daemon-start restart for the gateway, so a reboot cannot publish it before the post-Docker User Script restores the firewall.
4. Start API, workers, web, and gateway in dependency order through the fixed launcher. Require readiness with `Host: lil-orb.pax-kun.com`.
5. Change Nginx Proxy Manager only after the firewall and readiness checks pass.
6. Remove the temporary migration authorization only after transfer and rollback prerequisites have been recorded.

## Cutover and rollback

### New-installation owner bootstrap

Promote the first owner only after that person has registered and verified their email:

```powershell
docker compose --env-file .env -f infra/compose.yaml exec api python -m little_orbit_api.cli promote-admin owner@example.com
```

For releases through 1.1, the historical browser enrollment flow configured the first TOTP. In the 1.2 final state `/admin` is absent. Use Big Orbit's initial MFA setup and device-enrollment flow: re-enter the owner password, confirm the new TOTP, store the one-time recovery codes, create the app's non-exportable P-256 key, and finish its five-minute signed challenge. The promotion command never creates an account or bypasses email verification.

Existing production ownership and Big Orbit enrollment are migrated as database state; do not promote a replacement owner during the host move.

### Migration rollback boundary

Before `.14` accepts any write, rollback is the NPM upstream switch back to `.182` followed by restarting its frozen writer services. After `.14` accepts a write, never start the stale `little-orbit` project. Stop every service in that old project, keep its database/attachment volumes and secrets untouched, create an absolute empty bind-backed recovery root outside the checkout, and run the explicit reverse mode from the updated `.182` source:

```powershell
New-Item -ItemType Directory -Path D:\LittleOrbit\rollback-data
python infra/scripts/direct_migration.py `
  --direction rollback `
  --local-host 192.168.50.182 `
  --unraid-host 192.168.50.14 `
  --unraid-port 23 `
  --ssh-identity C:\protected\little-orbit-migration-ed25519 `
  --known-hosts C:\protected\little-orbit-migration-known-hosts `
  --local-env .env `
  --rollback-data-root D:\LittleOrbit\rollback-data `
  --confirm post-write-rollback-.14-to-.182-users-offline
```

Rollback rejects a backup identity argument and never copies or overwrites `.182` secrets. It requires the old production project to be fully stopped, refuses an existing `little-orbit-rollback` container or PostgreSQL volume, and records a durable `rollback-preparing` journal on `.14` before any local destination mutation. It then builds the updated attachment image and starts a fresh `little-orbit-rollback_postgres-data` volume. After it freezes the exact `.14` writers, the same single-transaction database restore, sibling-tree verification, and content-free inventory comparison run in reverse. Local promotion is followed by a durable `rollback-committed` transition while both host locks remain held. A pre-commit failure removes only the dedicated rollback project/data, restarts and proves the exact `.14` writers, and restores the forward-committed journal; a committed rollback preserves the local target and keeps `.14` frozen.

The recovery override binds only `127.0.0.1:18181` by default. Validate the restored API, sessions, attachments, releases, roles, and Alembic head in that isolated project before exposing it. Every later Compose invocation must retain the same project, base/override order, environment file, and non-secret recovery values:

```powershell
$env:ROLLBACK_DATA_ROOT = 'D:\LittleOrbit\rollback-data'
$env:LITTLE_ORBIT_ENV_FILE = (Resolve-Path .env)
$env:ROLLBACK_GATEWAY_BIND_ADDRESS = '127.0.0.1'
$env:ROLLBACK_GATEWAY_PORT = '18181'
$env:GATEWAY_INTERNAL_SUBNET = '10.253.182.0/28'
$env:GATEWAY_CADDY_IP = '10.253.182.2'
$env:GATEWAY_API_IP = '10.253.182.3'
docker compose --project-name little-orbit-rollback --env-file .env `
  -f infra/compose.yaml -f infra/compose.rollback.yaml up -d --wait api web gateway
```

Only after local validation may an operator bind that recovery gateway to `192.168.50.182:8180`, reapply and verify the `.182` firewall boundary, and point NPM back. Never start the stale project alongside it. A power loss between the two whole-directory promotions can leave one complete destination tree and one empty tree; the recovery stack remains unstarted and a retry fails closed rather than serving a mixture. Inspect and discard only the dedicated rollback project/root before retrying.

After cutover, verify HTTPS and WSS, both existing sessions, Big Orbit enrollment/session behavior, SMTP, first-party notification delivery, authorized attachment reads, ClamAV, full and ranged phone/Wear APK downloads, and forwarded-client identity. Reboot `.14` and repeat stack startup, firewall persistence, schedules, and GPU-lock checks. Produce a fresh target backup and pass the local restore drill.

Retain `.182` source code and signer recovery files. After a short validation window, removal of its old PostgreSQL and attachment volumes requires a new, explicit destructive approval and must occur before the agreed 24-hour duplicate-state limit. The migration plan does not itself authorize deletion.

The PowerShell firewall and operations wrappers remain only for `.182` recovery. Do not register their schedules alongside active Unraid User Scripts.

## Nginx Proxy Manager

Create one proxy host for `lil-orb.pax-kun.com`:

- Scheme: HTTP
- Forward hostname/IP: `192.168.50.14`
- Forward port: `8180`
- WebSocket support: enabled
- Block common exploits: enabled
- Certificate: Let's Encrypt for the exact hostname
- Force SSL and HTTP/2: enabled after certificate issuance succeeds

Keep `REGISTRATION_OPEN=false` while Mailpit is the configured SMTP service. Open registration only after an external SMTP delivery test confirms that verification and password-reset links use the public HTTPS origin.

Change only the upstream address from `.182` to `.14`; keep public DNS, certificate, and TLS settings unchanged. Test website pages, `/patch-notes`, `/patch-notes.xml`, `/.well-known/assetlinks.json`, `/api/v1/health/ready`, a real WebSocket upgrade, signup email delivery, and certificate renewal/recovery. Enable HSTS only after those checks and a rollback path succeed. The live NPM change is an explicit deployment action; screenshots or a saved draft are not proof that traffic works.

## Restart recovery

If forward migration is interrupted, do not start either copy manually. With schedules still disabled and the same pinned SSH inputs, run the recovery-only direction:

```powershell
python infra/scripts/direct_migration.py `
  --direction recover-forward `
  --local-host 192.168.50.182 `
  --unraid-host 192.168.50.14 `
  --unraid-port 23 `
  --ssh-identity C:\protected\little-orbit-migration-ed25519 `
  --known-hosts C:\protected\little-orbit-migration-known-hosts `
  --local-env .env `
  --confirm recover-interrupted-forward-.14-state
```

Under the shared local/remote migration exclusion, `preparing` removes only the fixed `.14` target copy and becomes a durable restart-required journal before `.182` is started and proved healthy. `committed` preserves `.14` and never starts `.182`; an absent journal is a no-op. Malformed or foreign state refuses recovery.

For an interrupted reverse migration, retain the fully stopped old `little-orbit` project and the exact fenced rollback root, then use `--direction recover-rollback` with confirmation `recover-interrupted-rollback-.182-state` and the same `--rollback-data-root`. `rollback-preparing` removes only the dedicated rollback project and allowlisted root children, restarts and proves `.14`, then restores its forward-committed journal. `rollback-committed` preserves the promoted `.182` copy and never restarts `.14`. A legacy forward-committed marker permits the same cleanup/restart path; malformed, absent, or foreign state fails closed.

The Unraid startup User Script runs only after the array and Docker are available. Reboot the host, then verify the `.14` address, direct cache mounts, NPM-only firewall scope, absent IPv6 listener, all health checks, public HTTPS, WSS, email, worker schedules, and one curated fallback pool while Ollama is stopped.

The internal `gateway-api` link reserves `10.253.14.2` for Caddy and `10.253.14.3` for FastAPI. Keep both assignments together with `TRUSTED_PROXY_IP`; this prevents a recreated API container from dynamically taking the trusted proxy address before Caddy starts. After a Compose recreation, inspect the resolved configuration and confirm both containers are healthy before testing forwarded-client throttles.

## Signed Android releases

Signing is not part of production Compose. On `.14`, use the Android builder with its digest-pinned JDK base to produce clean unsigned candidates, then the separate one-shot signer. The launcher records the resulting content-addressed image IDs and runs those IDs rather than mutable tags. The signer runs with `--network none`, a read-only root, all capabilities dropped, no Docker socket, a tmpfs work directory, and a read-only secret mount. Keep the product-specific encrypted signer bundle and its age identity separate because Android will reject an update signed by a replacement key.

The controlled launcher accepts only a clean committed source tree, empty candidate/output directories under `/mnt/cache/little-orbit-live/release-work/`, an encrypted bundle under `/mnt/cache/vault/little-orbit/android-signing/`, and an explicit age identity. It decrypts `release.p12`, `store-password`, `key-alias`, and `key-password` beneath `/dev/shm/little-orbit-signing/little-orbit.<run-id>`, passes passwords by file, and deletes plaintext through an exit trap:

```bash
/mnt/cache/little-orbit-deploy/repo/android-release/run-release.sh \
  /mnt/cache/little-orbit-deploy/repo \
  /mnt/cache/little-orbit-live/release-work/candidate-<run-id> \
  /mnt/cache/little-orbit-live/release-work/signed-<run-id> \
  /mnt/cache/vault/little-orbit/android-signing/little-orbit-signer.tar.age \
  /mnt/cache/little-orbit-secrets/android-signing-age-identity.txt
```

Before manifest creation, require the pinned Little Orbit certificate fingerprint and independently inspect phone and Wear package, version code, byte count, hash, and Wear feature. A failed password, alias, signer identity, forbidden QA marker, or metadata mismatch fails closed. Keep the original `.182` signer files unchanged until multiple disposable bundle restore/sign checks pass on `.14`.

Use the pinned absolute age path and the certificate-only mode for each non-signing custody check:

```bash
ANDROID_RELEASE_AGE_BIN=/mnt/cache/little-orbit-tools/bin/age \
  /mnt/cache/little-orbit-deploy/repo/android-release/run-release.sh --verify-bundle \
  /mnt/cache/little-orbit-deploy/repo \
  /mnt/cache/vault/little-orbit/android-signing/little-orbit-signer.tar.age \
  /mnt/cache/little-orbit-secrets/android-signing-age-identity.txt
```

It verifies the recovered PKCS12 private-key entry and pinned certificate without building or
signing an APK, writes no release output, and removes decrypted files from `/dev/shm` on every exit.
Use clean, committed disposable checkouts only beneath
`/mnt/cache/little-orbit-deploy/android-signing-drills/`; the product-specific launcher accepts one
exactly named child there and keeps the production source allowlist separate.

The PowerShell build remains a `.182` recovery path. Keep its PKCS12 release store and four `ANDROID_SIGNING_*` settings outside Git. Increment `versionCode` before every published update, set the intended `versionName`, then build and verify both targets:

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

Production 1.0.1 was published on 2026-09-19 at
`2026-09-19T18:19:24.932834Z`. Migration `0026`, one retained-history rebuild,
two reversible safe-duplicate archives, signed full/range downloads, RSS,
local/public readiness, and the code-23 compatibility floor were verified. The
owner waived the unavailable physical tablet soak; the missing evidence remains
recorded in the 1.0.1 verification report.

## 1.1.0 managed-watch release

Production 1.1.0 was published on 2026-09-19 at
`2026-09-19T20:35:33.306439Z` with phone version code 25, Wear version code 19,
compatibility floor 23, and no forced-update deadline. The generated manifest,
GitHub assets, staged bytes, immutable API row, public metadata, and web fallback
use the same artifact sizes and SHA-256 values.

The complete Android unit/lint/build matrix and independent signed-artifact
checks passed. Local and public metadata agreed; local and public complete phone
and Wear downloads matched the generated sizes and hashes; both 1,024-byte
public ranges returned `206` with correct totals. Patch notes, RSS, status,
showcase, local readiness, and public readiness passed after deployment.

The owner explicitly waived the unavailable physical Wear-device gate for this
release. First install, remembered update, same-version repair, private removal,
target switch, watch-side debugging revocation, offline Smooch, preference
revocation, 24-hour deletion, large text, tile, and both complications remain
unperformed on physical watch hardware. Keep those checks open in
[`WEAR-INSTALLER.md`](WEAR-INSTALLER.md) and the 1.1.0 verification record;
shipping approval is not evidence that they ran.

Future releases must still begin from the installed production pair where
possible and prove that page open, scheduled metadata work, and status refresh
do not request APK bytes. A later physical pass may close the missing evidence,
but it must not edit the immutable 1.1.0 release identity or imply the check was
part of this rollout.

## 1.1.1 watch-hardening release

The verified 1.1.1 release contains phone version code 26 and Wear version code
20, keeps the compatibility floor at phone code 23, and has no forced-update
deadline. The exact phone artifact is 37,658,658 bytes with SHA-256
`a80a06513239b459522b3043083efc0cfce9e96e63cadbaadc5d0f3e3d3f1768`;
the exact Wear artifact is 14,737,940 bytes with SHA-256
`b5f2af70402b6c8c5ff6feae91b5f23a32bd7c0ccea91b032ab705f8013d7f2b`.
Both use signing-certificate SHA-256
`43e83a420c7496ce9121339ab5bd6b01a6357161a83a95042ace56855bd89337`.

On 2026-09-19, the owner explicitly waived the remaining physical in-app
wireless-ADB wizard, second-controller-phone, complete passive-surface and
large-font, and production in-place upgrade observations as publication gates.
The missing checks remain documented in the 1.1.1 verification record and are
not treated as passed evidence. Publication must use the exact generated
manifest and must verify local and public metadata, complete and ranged phone
and Wear downloads, hashes, patch notes, RSS, and health after the immutable
release record is created.

Production 1.1.1 was published at `2026-09-19T23:45:53.67375Z`. Local and
public metadata matched the generated manifest. Complete phone and Wear
downloads from both endpoints matched the exact sizes and SHA-256 values, and
all four 1,024-byte range requests returned HTTP 206 with correct totals.
Download, patch notes, RSS, status, showcase, and readiness checks returned
HTTP 200. Release-service logs contained no traceback, unhandled, fatal, or
error match during the rollout window.

## 1.2.0 quiz intelligence and Big Orbit release

Production 1.2.0 was published at `2026-09-21T12:10:32.956306Z` after a coordinated encrypted backup and migrations `0027` through `0029`. PostgreSQL 17 uses the pinned pgvector 0.8.6 image. The secret-free context fetcher joins only its private worker link and bounded egress network, Ollama remains internal, and only gateway port 8180 is host-published.

At the owner's direction, the final v2-only administrator API was deployed directly rather than retaining or deploying a temporary `/v1/admin` compatibility route. Local and public `/admin` plus `/api/v1/admin/configuration` return 404; unauthenticated `/api/v2/admin/devices` returns 403. The exact Big Orbit 1.0.0 code-2 APK was installed and cold-launched on the Pixel and tablet, but the owner waived production two-device enrollment, revocation, alerts, and recovery observation and will perform that QA after release. Do not describe those recovery devices as enrolled until that later evidence exists.

The three Windows operations tasks are registered for the current interactive owner. A manual runner backup recorded a passing local encrypted pair, and a manual non-destructive restore recorded a pass, verified excluded private rows were empty, and removed its temporary database. The owner waived an off-host copy/restore and durable off-host Big Orbit signer backup until the replacement server is available. A same-disk passing drill is not off-host disaster-recovery evidence.

The immutable phone artifact is version 1.2.0 code 28, 37,695,087 bytes, SHA-256 `aaa8c98d452db6d87c687f25cd2630432b64481ab6753c2bdb7bdb5baa7dc04f`. The unchanged Wear 1.1.1 code-20 artifact is 14,737,940 bytes with SHA-256 `b5f2af70402b6c8c5ff6feae91b5f23a32bd7c0ccea91b032ab705f8013d7f2b`. Both use certificate SHA-256 `43e83a420c7496ce9121339ab5bd6b01a6357161a83a95042ace56855bd89337`. The compatibility floor remains 23 and `required_after` is absent.

Code 27 was signed but discarded before publication when deep inspection found a QA-only asset-name marker in production bytecode. Big Orbit code 1 was also discarded after the exact minified APK crashed during WorkManager initialization. Neither failed version code nor its bytes was reused. Public and local complete/range downloads, GitHub mirrors, patch notes, RSS, public pages, readiness, and rollout logs were verified against the final code-28 and Big Orbit code-2 artifacts.

## 1.3.0 themed quizzes and Big Orbit bootstrap release

Production 1.3.0 was published at `2026-09-24T02:33:46.511784Z` after an encrypted coordinated backup, a passing non-destructive restore drill, and migrations 0030 and 0031. The immutable artifacts are Little Orbit phone code 29, Wear code 21, and independently signed Big Orbit code 3. If any future signed candidate fails inspection or launch, increment the affected code and rebuild from a clean committed tree; never reuse failed bytes or a failed code.

Before migration, create and verify a coordinated encrypted database/attachment backup. Rehearse `0029 -> 0031 -> 0029 -> 0031` on an isolated PostgreSQL 17/pgvector database, then apply 0030 and 0031 in production. Confirm the worker synchronizes the reviewed knowledge manifest and exactly 2,190 reserve entries, records the configured `America/Los_Angeles` schedule, and leaves already published quiz coverage intact if Ollama, embeddings, or public context are unavailable. Do not reset consumed reserve rows.

The 1.3 coordinator uses a workspace-bounded relative-path helper compatible with the documented Windows PowerShell 5.1 invocation as well as PowerShell 7. Treat encrypted component files without a completed pair manifest as incomplete and never select them for restore.

The published 1.3.0 baseline used Saturday/Sunday 09:00 Pacific and one planned week, as recorded in its immutable release evidence. For the current Unraid migration source, verify Saturday at 01:00 `America/Los_Angeles` makes one cursor-bounded learning/planning job eligible and Sunday at 03:00 makes generation eligible. Under contention, require persistent six-hour retries without an `AiRun` claim or false failure; successful generation must publish only after fourteen days satisfy schema, theme/depth composition, safety, embedding, and semantic checks. Inspect Big Orbit for content-free queue, reserve-low, stale-context, and failed/fallback-run alerts. The typed regeneration action may replace only future unanswered global pools.

For every fresh Big Orbit device, run `python -m little_orbit_api.cli bootstrap-admin <email>` inside the trusted API environment and transfer the displayed PIN out of band. Do not store it in a deployment log. Confirm five wrong attempts and ten-minute expiry fail closed, a second PIN revokes the first unfinished setup, and bootstrap bearer tokens cannot call normal administrator routes. On the first owner, complete QR-based TOTP and retain recovery codes securely; on later devices, confirm existing MFA material is unchanged. Keep at least one tested recovery path before revoking an older device.

Build release variants only after both repositories' `VERSION` and release-train contracts agree. Inspect Little Orbit and Big Orbit outputs for QA packages, labels, endpoints, keys, metadata, or bundled smoke APKs. Publication verified exact complete and ranged first-party downloads, matching GitHub mirror digests, public metadata and pages, healthy readiness, and a clean rollout log window. The compatibility floor remains phone code 23 and `required_after` is unset.

At the owner's expedited-release direction, exact APK cold launches were completed on API 36 phone/Big Orbit and API 34 round-Wear emulators. Physical phone/Wear upgrade, two-partner quiz, and fresh/returning Big Orbit enrollment observations remain deferred live QA and must not be described as passed.
