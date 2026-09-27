# Unraid migration verification record — 2026-09-26

## Scope and current state

This record covers preparation to move Little Orbit from the Windows host at `192.168.50.182` to Unraid at `192.168.50.14`, share the target RTX 4060 cooperatively with Scriptarr, and make `.14` the isolated Android build/signing host.

As of this record, source implementation, the isolated target rehearsal, Scriptarr's lock-aware images and exact-file arbitration checks, and Android signer-custody checks are complete. Scriptarr's live Oracle and Raven containers now mount the required exact lock file. The production database and attachments have **not** been streamed, migration `0032` has **not** been applied to production, Nginx Proxy Manager still points to `.182:8180`, and no `.182` database or attachment volume has been deleted. `.182` remains the live Little Orbit host.

## Implemented in source

- `infra/compose.unraid.yaml` defines direct Unraid bind-backed state, the fixed `10.253.14.0/28` private gateway link, and the shared GPU coordinator mount.
- `infra/scripts/unraid-stack.sh` fixes production Compose order to base, GPU, then Unraid.
- The Unraid bootstrap, firewall, User Scripts dispatcher, backup, restore-drill, and operations runner use fixed paths and operation kinds. Only the five-minute pending runner may return successful `already_running`; backup and drill collisions wait boundedly or fail.
- `infra/scripts/direct_migration.py` accepts only the fixed `.182`/`.14` pair and SSH port 23, requires pinned host-key input plus direction-specific confirmation, and has no archive output. Forward mode requires the protected backup identity; rollback rejects it, preserves `.182` secrets/old volumes, and restores into the fresh `little-orbit-rollback` project. Both directions stop exact writers, reject running AI claims, use single-transaction database restore, verify sibling-staged attachments/releases, and emit matching content-free source/destination inventories before whole-tree promotion. Durable forward/rollback journals support explicit, lock-held recovery after controller or host interruption without guessing which copy owns writes.
- Migration `0032` and the content-free AI work queue implement persistent scheduling, lease fencing, and shared-GPU acquisition before an AI run claim.
- The Android release directory separates a clean unsigned builder from a network-disabled one-shot signer, keeps secret plaintext in tmpfs, and verifies product policy before manifest output.
- ADR 0047 records Unraid persistence, exact streaming, cooperative GPU arbitration, local-only recovery limits, and signing isolation.

These bullets describe repository state, not a successful live deployment.

## Local verification completed

The following checks passed before this record was written:

| Check | Result |
|---|---|
| `python -m pytest infra/scripts/tests -q` | 123 passed; one capability skip |
| Full API/AI suite with disposable PostgreSQL 17/pgvector | 259 passed; one Windows symbolic-link capability skip; 22 warnings |
| Direct-migration split suite | 81 passed |
| Restart-safe migration recovery contract | 23 passed |
| PostgreSQL role/ACL policy checks | 9 passed; pinned PostgreSQL 17 normalization rehearsal passed |
| Focused PostgreSQL queue integration | 4 passed, including stale-token commit fencing |
| API/AI suite without disposable PostgreSQL | 207 passed; 43 integration skips; 22 warnings |
| Ruff across services, infrastructure, and Android release helpers | Passed |
| Strict mypy | 211 source files passed |
| Web `check`, tests, and production build | Passed; 40 tests |
| Little Orbit Android domain/data/mobile/Wear unit and debug lint tasks | Passed; 153 tasks |
| Big Orbit debug unit, smoke assembly/lint, and release lint tasks | Passed; 83 tasks |
| Little Orbit Android release-helper tests | 19 passed |
| Big Orbit Android release-helper tests | 17 passed |
| Ordered base/GPU/Unraid `docker compose config` with target values | Rendered successfully |
| Rendered published ports | Gateway only, `192.168.50.14:8180` |
| Rendered live PostgreSQL path | `/mnt/cache/little-orbit-live/postgres` |
| Rendered GPU lock path | `/mnt/cache/gpu-coordinator/gpu.lock` |
| Rendered gateway link | `10.253.14.0/28`, Caddy `.2`, API `.3`, trusted peer `.2` |
| `python infra/scripts/check_docs.py` | 130 repository-owned Markdown files inventoried; local links valid |
| `npx --yes markdownlint-cli2 "**/*.md"` | 0 issues |
| Mermaid CLI 12.0.0 render of `docs/NETWORK-FLOW.md` | All 27 diagrams rendered successfully |

The focused AI adapter suite also exercises transport timeout and HTTP 500/OOM responses and proves that both collapse to a bounded content-free `OllamaFailure`; untrusted response detail is not surfaced. PostgreSQL queue integration covers persistent six-hour retry timing, stale lease takeover/fencing, ordering, and completed legacy runs. Direct migration tests cover atomic forward/rollback journals, exact-writer recovery, malformed/foreign-state refusal, and a real `prepare_forward` call proving all required target-local images build before the source stop attempt. Static database validation covers role flags, membership, database/schema/object/default ACLs, and malicious extra-privilege normalization without exposing passwords or row values. The local tests do not constitute production cutover, physical-device, or reboot evidence.

## Isolated `.14` stack rehearsal

An isolated Compose project on `.14` used synthetic secrets and an empty synthetic database. It reached Alembic head `0032`; PostgreSQL, API, web, and gateway were healthy; readiness with `Host: lil-orb.pax-kun.com` returned `200`; and an untrusted Host returned `400`. The only listener was the rehearsal's explicitly loopback-bound gateway. The rehearsal was then removed with its disposable volumes, and target port `8180` was free again.

The first rehearsal exposed a real PostgreSQL startup race: `pg_isready` without `-h` could accept the image's temporary socket-only initialization server, allowing `database-bootstrap` to start while that server shut down. The production health check now probes `127.0.0.1`, and a regression test requires that TCP form. The clean rerun passed.

Target ClamAV cache preparation used the immutable image digest `clamav/clamav@sha256:b12ef8fefddbba7d88de59bea8a32622f365339154adf02d38fd089112e6745a` in a read-only, capability-dropped one-shot container. Database self-tests passed for daily 28135, main 63, and bytecode 339; no preflight container remained running.

After Scriptarr's idle-unload proof, Little Orbit's model preparation acquired the same host lock, required empty compute and process-monitor output, and used `ollama/ollama@sha256:a5409cb903d30f9cd67e9f430dd336ddc9274e16fd78f75b675c42065991b4fd`. The local Ollama registry exactly matched generation digest `0edcdef34593eac1aa2be9c7d06c432dcf81945adca5eca2f27662c18f168ba0` and embedding digest `0a109f422b47e3a30ba2b10eca18548e944e8a23073ee3f3e947efcf3c45e59f`; `ollama ps` was empty. The one-shot container was removed, GPU output was empty, and lock inode `3177412` was unchanged before release.

## Scriptarr shared-GPU rollout

Scriptarr now runs the lock-aware images below on `.14`:

- Oracle `docker.darkmatterservers.com/the-noona-project/scriptarr-oracle@sha256:70723d40226167b3165454c0d65e41e849c330de126747049b6077d65b63183b`
- Raven `docker.darkmatterservers.com/the-noona-project/scriptarr-raven@sha256:0fca279ec0d942a0ec285931d7b91d3069c94bd039f1895eeed2a9b1b127dd50`
- Warden local tag `scriptarr-warden:gpu-lockfile-20260926`, immutable local image ID `sha256:4a92ef6460590c4e3b1d084541cd37e73fc536b57c91584245e37fa6fc7e7108`
- Sage `docker.darkmatterservers.com/the-noona-project/scriptarr-sage@sha256:fc9d0deaa6ef9e191d1fd6304b505018e83b9a8ee7fd4f8ce2758c5e2acd89b3`

The deployment preserved the one stable lock inode, `3177412`, as root:`2000` mode `0660` with one link and zero bytes. Oracle and Raven now bind that exact host file read/write at `/run/gpu-coordinator/gpu.lock` and have supplementary GID `2000`; no coordinator-directory bind remains. Sage and Warden carry `America/Los_Angeles`; the durable update task remains `0 */6 * * *` in that timezone. The corrected Warden image contains service-plan SHA-256 `29fe9ffabfe9bda73b467282200ae8583bd0f9269d38dc6eeaa4ecd8cc6dd694` and storage-layout SHA-256 `ac69d760658f25a1ed18d7f294669af7d30a4ed97323c6af91f4d1e4d49926e4`. Its configured edge service set is exactly Moon, Sage, Raven, and Oracle; all four plus Warden reconciled healthy. The stopped legacy Vault, Portal, and MySQL containers are not in that managed-service set and are not counted as current health failures. Passive Oracle health/status/model-list calls left VRAM empty. Under a host-held lock, a real synthetic Oracle request returned the graceful `gpu_busy` fallback without taking a lease. Raven's exact-file NVENC boundary returned retry exit `75` and zero output while locked, and the same exact lock became obtainable after release. The Warden suite passed 84 tests and the bounded production release verifier passed.

No synthetic live library title was inserted merely to demonstrate Raven's durable queue. Durable `gpu_busy` queue/resume behavior is covered by Raven's service tests; the live exact-file proof is limited to the NVENC wrapper's busy result and post-release lock acquisition, not a manufactured queued encode. During the earlier stable-inode rollout phase, a real Oracle request containing only `Repeat exactly: synthetic-oracle-check.` completed HTTP `200` in 127.690 seconds; its reply was discarded and never printed. LocalAI was the sole GPU compute process at 4,932 MiB and exclusively held the shared lock. Passive status polling did not reload it: Oracle recorded `idle_unloaded` 901 seconds after demand, after which GPU process views were empty and the unchanged lock inode was obtainable. After the exact-file rollout, passive checks, exact mount/inode evidence, host-held contention, Oracle fallback, post-release acquisition, and empty GPU state were repeated; a second 901-second demand/unload cycle was not manufactured.

The private registry was unavailable during the corrected Warden rollout, so the running Warden uses the unique local tag and immutable local image ID above rather than a registry digest. The earlier registry-pinned Warden digest remains only a rollback reference. Before treating this image as portable or rebuilding `.14`, publish the corrected image to the private registry, capture its registry digest, replace the local tag, and repeat reconciliation. The live Warden template now uses a root-only runtime environment file and contains no inline variable entries. Credentials that appeared in the stale template or diagnostic output still require coordinated rotation; no values are recorded here.

## Android build and signer custody on `.14`

The latest hardened drill images captured on `.14` are:

- Little Orbit builder `sha256:8f2e35069b23c1f8b8e8a34a3e4b21c7d98fcb7676ae336ccbca86b8c40f0230`
- Little Orbit signer `sha256:01e1abfa4c7eb14f8a880f8b796f21784db1ad6443caa498045205a1fde661d5`
- Big Orbit builder `sha256:3debe5a83278c351bda6e3a2809634ffe0d4e6b7a21c6571555b04590bf3d0b5`
- Big Orbit signer `sha256:9ce2667b771eae452160e8bb6ce41253ae72db73e1eb2118cbeb66bd006e35ca`

Each production encrypted signer bundle passed certificate-only restore twice through an immutable signer image with no network, a read-only root, dropped capabilities, and tmpfs secret handling. Little Orbit matched `43e83a420c7496ce9121339ab5bd6b01a6357161a83a95042ace56855bd89337`; Big Orbit matched its independent `04dc3502933faaa99dfd6641acc52b2bd71c9895087cb3060e3ce92dd8406f8c`.

Disposable end-to-end signing through the hardened runners produced only these unpublished test artifacts:

| Product | Version / code | Bytes | SHA-256 |
|---|---|---:|---|
| Little Orbit phone | `0.0.0-drill-20260926` / `900001` | 37,692,367 | `ca5c8673be67c77d228fd218149892f71ae3ffff5df3abfbc908ce91ae1909eb` |
| Little Orbit Wear | `0.0.0-drill-20260926` / `900002` | 14,738,580 | `4313315aed23765352982a81a34a3c9514d4a565d5a3dbed377800f61b4f4d45` |
| Big Orbit | `0.0.0-drill-20260926` / `900003` | 2,485,998 | `e1ed32462270e253d8c2d7b6b61b01a0500128c5a2db1609e2e853686e146f39` |

The Little Orbit artifacts used disposable certificate `713e533bbd1b81195dd9e25fb739fd759714d5c2eeb516fa02672228b18a09b3`; Big Orbit used independent disposable certificate `268d72c0788052dfde6aa4451977f8b73815522cdb435570530a777301d1993d`. Independent `aapt` inspection matched each package and version and confirmed the signed Wear APK declares `android.hardware.type.watch`. Full signing ran in signer containers with no network, a read-only root, and all capabilities dropped. No production APK was signed.

For both products the correct disposable bundle was accepted, while a wrong store password, wrong key password, wrong alias, and wrong certificate were rejected without printing secret values. A concurrent Warden build left Docker container creation wedged during this final negative matrix. The checks therefore invoked the exact OpenJDK 17 runtime and compiled `SignerCertificateVerifier.class` from each captured signer image's read-only BTRFS layer rather than claiming that those final negative cases ran inside a newly created container. The end-to-end signing isolation above did run through the hardened containers.

Production signer-bundle hashes were unchanged, the target's pre-migration historical-release snapshot remained at zero files, and both drill repositories were clean. Cleanup left no tmpfs signing/source directory, disposable vault bundle, drill checkout, release-work output, or related process. The original `.182` signer files remain untouched as recovery copies; this evidence does not authorize their deletion.

## Read-only `.14` preflight evidence

The authenticated Unraid dashboard and terminal showed:

- Unraid 7.3.1, array started, parity reported valid, and no active BTRFS operation at inspection time.
- Approximately 538 GB free on cache and 227 GB free through the array-backed user share at the latest CLI preflight. Disk 1 was about 90% used and disk 2 about 88% used, so capacity and retention must be rechecked immediately before transfer.
- Docker Compose 2.40.3, with `jq`, `flock`, and `git` available on the host.
- No host `age` or Python 3 binary. The bootstrap therefore installs a checksum-pinned `age` binary, while migration Python executes from the source or application container rather than relying on host Python.
- The route table already assigns `172.30.0.0/16` to `pterodactyl0`; this rejects the earlier `172.30.14.0/28` proposal. `10.253.14.0/28` was not present in the observed route table and is the configured replacement, subject to a final collision check.
- Scriptarr Oracle, Raven, Moon, Warden, and Sage are healthy after the coordinated image rollout. The corrected Warden is currently identified by a unique local tag plus immutable local image ID because the private registry was unavailable; the prior registry-pinned Warden remains a rollback reference only. Old uncoordinated Oracle and Raven images must not be started once Little Orbit GPU work is enabled.
- The Little Orbit jump is first in `DOCKER-USER`. Applying the firewall twice alternated only the owned A/B chain, retained the same hash for every unrelated `DOCKER-USER` rule, and left no IPv6 listener. A temporary IPv4 container listener on `.14:8180` was unreachable from `.182`; it and its listener were removed immediately afterward. The allowed `.6` path still requires end-to-end proof when NPM is switched.

No terminal output containing a secret, row value, attachment name, signing password, or precise location was collected for this record.

The live `.182` database was also checked through the content-free security inventory while it remained at migration `0031`: all 74 public tables and the exact reviewed role/ACL policy validated. No row values, hashes, filenames, or relationship content were emitted.

## Required before source freeze

- [ ] Recheck the static/DHCP reservation, SSH port 23 host key, temporary migration key, free capacity, NVIDIA runtime, port 8180, IPv6 listeners, and `10.253.14.0/28` availability.
- [ ] Configure `.14` for exact `America/Los_Angeles`, pass `require_unraid_pacific_timezone`, install the User Scripts,
  and confirm the daily 08:00 plus Tuesday 07:00 entries. A mismatched configured identifier or effective
  `/etc/localtime` must make installation and direct wall-clock dispatch fail nonzero.
- [x] Build and migrate an isolated target project with synthetic state, refresh ClamAV, and pre-pull/verify both pinned Ollama models under the shared lock.
- [x] Finish Scriptarr's real demand and 900-second idle unload with exclusive residency plus post-unload lock/GPU proof. Lock contention, graceful Oracle fallback, the NVENC wrapper, and service-level durable queue behavior also passed; crash/reboot recovery remains a post-cutover gate.
- [x] Replace Scriptarr Oracle and Raven's live coordinator-directory mounts with exact `/run/gpu-coordinator/gpu.lock` file binds through the corrected Warden plan; repeat passive-health, exact mount/inode, contention, post-release acquisition, and empty-GPU checks. The earlier full 901-second idle-unload proof used the same stable host inode; the narrower exact-file repetition is recorded above.
- [x] Run Little Orbit API/AI tests, Ruff, mypy, web checks/tests/build, Android unit/lint tasks, Compose checks, backup/restore safety tests, and Android release-helper tests.
- [x] Verify Pacific daylight-saving boundaries, ordered six-hour retry persistence, contention before `AiRun` claim, stale-lease fencing, administrator AI queueing, fourteen-day coverage, and timeout/OOM handling in focused tests.
- [x] Complete disposable-key end-to-end signing for Little Orbit and Big Orbit plus wrong-store-password, wrong-key-password, wrong-alias, wrong-certificate, redaction, independent metadata, and zero-residue cleanup checks on `.14`, with the final negative-verifier Docker caveat recorded above.
- [ ] Confirm both people are off the app and disable `.182` schedules.
- [ ] Create a fresh ordinary privacy-filtered encrypted backup and pass its restore drill.
- [ ] Record source commit/image digests, migration head `0031`, privacy-safe table counts including feedback and feedback-operation rows, attachment aggregate digest, and every immutable-release size/hash.
- [ ] Stage schema-0032-compatible source on `.182` for rollback without starting it.

## Required for exact transfer and cutover

- [ ] Require an empty target database and attachment staging area.
- [ ] Stop every source writer and direct-stream the complete logical database, frozen attachments, and immutable releases through pinned SSH without retaining the streams.
- [ ] Match exact pre/post row counts, attachment digest, release sizes/hashes, roles/grants, and Alembic head `0032`.
- [ ] Start target dependencies in order and pass readiness with `Host: lil-orb.pax-kun.com`.
- [ ] Apply and inspect the NPM-only `DOCKER-USER` rule; prove another LAN source and IPv6 cannot reach port 8180.
- [ ] Change only Nginx Proxy Manager's upstream from `.182:8180` to `.14:8180`.
- [ ] Verify public HTTPS/WSS, existing sessions, Big Orbit enrollment/session behavior, SMTP, first-party notifications, authorized attachments, ClamAV, full/ranged APK downloads, and forwarded-client identity.
- [ ] Prove no simultaneous Little Orbit Ollama/embedding, Scriptarr LocalAI, or Raven NVENC GPU processes.

## Required after cutover

- [ ] Produce a fresh target encrypted backup and pass the local Tuesday-style restore drill.
- [ ] Reboot `.14` and reverify array/Docker ordering, Compose health, firewall persistence, schedules, GPU lock behavior, and public service health.
- [ ] Establish and restore an encrypted off-host runtime copy. The Unraid parity-array backup remains local-only evidence until then.

Before `.14` accepts a write, rollback is an NPM upstream reversal plus restarting the frozen source. After a target write, `.182` is stale: the explicit reverse-stream command must restore current `.14` state into the separate fresh `little-orbit-rollback` project and match table, schema, attachment, and release evidence before that project can be considered for traffic. The old `little-orbit` project must never restart. Deleting its database or attachment volumes requires a separate explicit destructive approval; this implementation request is not that approval.
