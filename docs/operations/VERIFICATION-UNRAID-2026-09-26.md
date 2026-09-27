# Unraid migration verification record — 2026-09-26 to 2026-09-27

## Scope and current state

This record covers preparation and the live application-cold move of Little Orbit from the Windows host at `192.168.50.182` to Unraid at `192.168.50.14`, cooperative use of the target RTX 4060 with Scriptarr, and use of `.14` as the isolated Android build/signing host.

As of 2026-09-27, the direct database, attachment, and immutable-release stream is committed; production is at migration `0032`; Nginx Proxy Manager points to `.14:8180`; and `.14` is the authoritative writer. Public pages, readiness, release metadata, complete and ranged APK delivery, forwarded-client identity, ClamAV health, schedule activation, the shared lock inode, empty Ollama/VRAM state, child-role credential rotation, and fresh local encrypted backup/restore drills have passed the checks recorded below. The old `.182` writer services remain stopped, and no `.182` database or attachment volume has been deleted. Existing authenticated sessions, authenticated WSS, Big Orbit behavior, SMTP and notification delivery, authorized attachment reads, physical-device QA, external cellular/WAN reachability, and final reboot recovery remain open; this record does not claim those checks passed.

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
| `python -m pytest infra/scripts/tests -q` | 150 passed; one capability skip |
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
- The host is currently configured with `USE_DHCP="yes"`; the router-side reservation is not observable from Unraid and still requires operator confirmation before source freeze.
- Approximately 538 GB free on cache and 227 GB free through the array-backed user share at the latest CLI preflight. Disk 1 was about 90% used and disk 2 about 88% used, so capacity and retention must be rechecked immediately before transfer.
- Docker Compose 2.40.3, with `jq`, `flock`, and `git` available on the host.
- No host `age` or Python 3 binary. The bootstrap therefore installs a checksum-pinned `age` binary, while migration Python executes from the source or application container rather than relying on host Python.
- The route table already assigns `172.30.0.0/16` to `pterodactyl0`; this rejects the earlier `172.30.14.0/28` proposal. `10.253.14.0/28` was not present in the observed route table and is the configured replacement, subject to a final collision check.
- Scriptarr Oracle, Raven, Moon, Warden, and Sage are healthy after the coordinated image rollout. The corrected Warden is currently identified by a unique local tag plus immutable local image ID because the private registry was unavailable; the prior registry-pinned Warden remains a rollback reference only. Old uncoordinated Oracle and Raven images must not be started once Little Orbit GPU work is enabled.
- The Little Orbit jump is first in `DOCKER-USER`. Applying the firewall twice alternated only the owned A/B chain, retained the same hash for every unrelated `DOCKER-USER` rule, and left no IPv6 listener. A temporary IPv4 container listener on `.14:8180` was unreachable from `.182`; it and its listener were removed immediately afterward. The allowed `.6` path still requires end-to-end proof when NPM is switched.
- The authenticated Nginx Proxy Manager table contains one `lil-orb.pax-kun.com` row, still online at `http://192.168.50.182:8180`; no NPM setting has been changed.

No terminal output containing a secret, row value, attachment name, signing password, or precise location was collected for this record.

The live `.182` database was also checked through the content-free security inventory while it remained at migration `0031`: all 74 public tables and the exact reviewed role/ACL policy validated. No row values, hashes, filenames, or relationship content were emitted.

The first live bootstrap attempt found that `.14`'s persisted array-only backup-share file had not yet refreshed the running `shfs`: its content-free placement sentinel landed on cache, and the physical-placement verifier stopped immediately. The misplaced sentinel and its otherwise empty directory were removed, the exact same share policy was applied through Unraid's local management command, and a repeat sentinel landed on one array disk with no cache copy. That management path canonically rewrites share files with CRLF endings; the exact post-apply validator accepts only the same fixed values under LF or CRLF and rejects duplicates or alternate values. Bootstrap now performs the runtime apply and revalidation before creating any share content, with fail-closed request-rendering tests for both direct-cache and array-only policy shapes. A live run of the corrected bootstrap completed and preserved exactly one array sentinel with no cache copy.

The first inactive User Scripts install also exposed an empty-host no-op bug: an absent `customSchedule.cron` inherited the failed file-test status and made `install` exit nonzero after writing only disabled schedule metadata. The no-file branch now returns explicit success, has a regression test, and a corrected live install reported `installed-inactive`; no Little Orbit cron line or container was activated.

The selected code-only snapshot contains no runtime environment, signer store, backup identity, or SSH key. Its clean rollback and `.14` deployment checkouts have a matching mode-independent blob/path digest. Earlier staging attempts remain preserved as recoverable code-only directories and are not selected for migration.

Immediately before the source freeze, the three `.182` production schedules were disabled and verified not running. The first fresh backup attempt exposed Windows PowerShell 5.1 native-argument removal of JSON quotes in the operations runner; database commands now stream SQL through `psql` stdin. The first restore attempt then exposed the .NET Framework redirected-stdin UTF-8 preamble corrupting otherwise binary-safe PostgreSQL and attachment streams. The shared binary pipeline now creates destination stdin under a BOM-free encoding, and restore cleanup is armed before the restore command can fail. The exact leaked disposable database from that failed attempt was removed after name and count validation. A newly generated encrypted pair passed two restore drills with matching pair-manifest SHA-256 `7fc7cb833f1373aa94b9d4f202157190b0ff454c3e52c3555945c917bf83ab95`; schema, excluded private rows, and the attachment manifest verified, no drill database remained, and public-host source readiness returned HTTP 200. The earlier failed run remains visible as failed operational evidence and is not treated as a valid drill.

The first real pre-freeze attachment inventory then found that the isolated one-shot command had been given `migration_inventory.py` without its local security dependency. File hashing now lives in a self-contained one-shot module, while the host-only database/security comparison remains separate. Captured subprocess output is decoded explicitly as UTF-8 rather than the Windows locale. An isolated-process regression and the live read-only helper both passed: schema head `0031`, 74 public tables, one feedback row, one feedback-operation row, one attachment of 353,543 bytes with aggregate SHA-256 `03bb5db2e663c8fb94ce9b437f4cd99dd284f7470f7221960353722f54e89395`, and all immutable release sizes/hashes were emitted without content inspection. The exact frozen inventory remains the authority for transfer comparison.

## Live transfer and cutover evidence — 2026-09-27

The application-cold direct migration completed without retaining a full database or attachment archive. Every source writer remained stopped after commit. The destination reached Alembic head `0032` with 75 public tables; the complete source/destination table inventory, normalized roles/grants, one feedback row, one feedback-operation row, attachment evidence, and immutable-release evidence matched under the migration verifier. The destination retained one attachment of 353,543 bytes with aggregate SHA-256 `03bb5db2e663c8fb94ce9b437f4cd99dd284f7470f7221960353722f54e89395`. All 53 immutable release files matched their frozen source sizes and hashes. The new content-free `ai_work_queue` began empty as required.

The target started its dependencies and writers through the fixed base/GPU/Unraid launcher. Every long-running service with a configured health check was healthy, target-local readiness with `Host: lil-orb.pax-kun.com` returned `200`, and only `192.168.50.14:8180` was published. The owned `DOCKER-USER` boundary admitted `.6`, rejected a direct `.182` request by timeout, exposed no IPv6 listener, and left the content hash of unrelated filter rules unchanged.

The single Nginx Proxy Manager row for `lil-orb.pax-kun.com` changed only its forward address from `192.168.50.182` to `192.168.50.14`; scheme HTTP, port 8180, certificate, WebSocket support, exploit blocking, and other settings were preserved. This LAN cannot hairpin the router's public port 443, so post-cutover TLS checks used NPM's LAN listener at `.6:18443`, which maps to the same NPM HTTPS path as WAN port 443 while retaining the public hostname and certificate. Through that listener all of these returned `200`:

- `/`
- `/status`
- `/patch-notes`
- `/patch-notes.xml`
- `/.well-known/assetlinks.json`
- `/download`
- `/api/v1/health/ready`
- `/api/v1/releases/current`

Three independent external check-host nodes timed out for Little Orbit, and the same three nodes timed out for the unchanged `pax-kun.com` control. The LAN's observed WAN egress address was `67.185.205.68`, while the DNS A result used by `pax-kun.com` and the `lil-orb` CNAME resolved to `67.185.206.35`. External WAN validation is therefore blocked by stale DNS outside the `.14` NPM-upstream change. No DNS change was authorized or made, and the external-network gate remains open.

Current release metadata remained version 1.3.0, phone code 29, with the expected first-party phone and Wear URLs. Complete downloads through the same NPM TLS listener reproduced the immutable phone size 37,696,175 bytes and SHA-256 `c5c879d458719e3ed27e5bdda38823d839600141ca08ff0d8967356df0d623e9`, plus Wear size 14,737,944 bytes and SHA-256 `0f0f0f221d80bbb5fc9db70773d8980b5b40136251df2fe4e64c8b3530e985cf`. Independent 1,024-byte requests returned `206 Partial Content`, exact total `Content-Range` values, matching checksum headers, and immutable cache headers for both artifacts.

The first web-surface probe returned an empty `502` while API readiness remained `200`. Read-only tracing localized the fault to the Caddy-to-web hop: a pre-existing Scriptarr `DOCKER-USER` rule rejects port 3000. Little Orbit's private web hop was repaired to use its reserved port 3014, the gateway was recreated, and the complete matrix above then passed. No Scriptarr rule was changed or flushed.

A content-free forwarded-identity probe from client `.182` through NPM `.6` proved that Caddy accepted forwarding only from its expected `.6` peer and FastAPI resolved the original client as `.182`. An unauthenticated WSS upgrade reached the application and failed closed with `403`; no authenticated WSS session was exercised, so authenticated socket continuity remains open.

The stable GPU lock remained inode `3177412` at the host and inside the Little Orbit worker, Ollama, Scriptarr Oracle, and Scriptarr Raven consumers. Ollama reported no loaded model and the host GPU process view was empty after cutover. This proves the exact shared-file boundary and empty post-cutover state, not a simultaneous live Little Orbit/Scriptarr workload. ClamAV was healthy. The Pacific User Scripts entries were activated only after `.14` became authoritative: pending typed operations every five minutes, encrypted backup daily at 08:00, and restore drill Tuesday at 07:00.

The fresh target backup completed at `20260927-134838` with this exact local encrypted pair and manifest:

- `/mnt/user/little-orbit-backups/postgres/little-orbit-20260927-134838.dump.age`
- `/mnt/user/little-orbit-backups/attachments/little-orbit-attachments-20260927-134838.tar.age`
- `/mnt/user/little-orbit-backups/manifests/little-orbit-pair-20260927-134838.json`

The networkless restore drill selected that pair, reached schema `0032`, matched pair-manifest SHA-256 `67a3f82f62d5ad22cb2c810ebbd3090643bff425b65222da5ab563253a412879`, and confirmed that raw coordinates, collection-health snapshots, attributable feedback, feedback operations, and anonymous raw reviews were absent. Its evidence records `off_host_copy=false`; the passing drill is local recovery evidence only.

An operational process inspection exposed the API, worker, media, and backup PostgreSQL role passwords because the earlier bootstrap passed them as `psql --set` command arguments. No owner password was present in that command. All four child credentials were therefore treated as compromised. The bootstrap now sends them through `\getenv` definitions on psql stdin, and the retained one-shot command contains no password argument. The secrets share root was also corrected from Unraid's share ownership to exact root:root mode `0700`; `runtime.env` remains a single-link root:root mode-`0600` file.

The checked-in host-locked rotation command exercised its rollback boundary twice before commit. The first pre-mutation attempt rejected a zero-byte secure staging file because GNU `stat` described it as a `regular empty file`; the empty file was removed and production never changed. The second attempt installed new roles internally but rolled back before publication because its verifier used PostgreSQL's explicitly trusted loopback rule. The corrected verifier crosses the private Compose network through host `postgres`, where SCRAM is required, and tests forbid a return to loopback. Final operation `ccb5efb6b867d9d5164e933dac002017` committed after new-accept, old-reject, new-accept checks for all four roles, firewall preparation, gateway recreation, and post-start firewall verification. A separate stdin-only probe using the frozen `.182` values confirmed all four retired credentials are rejected. The content-free journal is `state=committed`, credential staging is absent, the gateway restart policy is `no`, and direct plus NPM-path readiness both return `200`.

The post-rotation target backup completed at `20260927-151434`:

- `/mnt/user/little-orbit-backups/postgres/little-orbit-20260927-151434.dump.age`
- `/mnt/user/little-orbit-backups/attachments/little-orbit-attachments-20260927-151434.tar.age`
- `/mnt/user/little-orbit-backups/manifests/little-orbit-pair-20260927-151434.json`

Its networkless restore drill reached schema `0032`, verified the private-row exclusions and attachment manifest, and matched pair-manifest SHA-256 `d3be4284fc2bb480239493fe5e6adf749942f1b808e71492ba066db7f3ec9dda`. It also records `off_host_copy=false` and does not close the off-host recovery gate.

## Pre-freeze gates and evidence

- [ ] Independently confirm the router-side `.14` reservation. The reservation was not observable from Unraid; the SSH port 23 host key and temporary key, capacity, NVIDIA runtime, port 8180, IPv6 listeners, and `10.253.14.0/28` availability were rechecked before freeze.
- [x] Configure `.14` for exact `America/Los_Angeles`, pass `require_unraid_pacific_timezone`, install the User Scripts
  in inactive mode, and verify the fixed every-five-minute, daily 08:00, and Tuesday 07:00 Pacific activation
  templates. A mismatched configured identifier or effective `/etc/localtime` makes installation and direct
  wall-clock dispatch fail nonzero. The inspected entries were activated after cutover.
- [x] Build and migrate an isolated target project with synthetic state, refresh ClamAV, and pre-pull/verify both pinned Ollama models under the shared lock.
- [x] Finish Scriptarr's real demand and 900-second idle unload with exclusive residency plus post-unload lock/GPU proof. Lock contention, graceful Oracle fallback, the NVENC wrapper, and service-level durable queue behavior also passed; crash/reboot recovery remains a post-cutover gate.
- [x] Replace Scriptarr Oracle and Raven's live coordinator-directory mounts with exact `/run/gpu-coordinator/gpu.lock` file binds through the corrected Warden plan; repeat passive-health, exact mount/inode, contention, post-release acquisition, and empty-GPU checks. The earlier full 901-second idle-unload proof used the same stable host inode; the narrower exact-file repetition is recorded above.
- [x] Run Little Orbit API/AI tests, Ruff, mypy, web checks/tests/build, Android unit/lint tasks, Compose checks, backup/restore safety tests, and Android release-helper tests.
- [x] Verify Pacific daylight-saving boundaries, ordered six-hour retry persistence, contention before `AiRun` claim, stale-lease fencing, administrator AI queueing, fourteen-day coverage, and timeout/OOM handling in focused tests.
- [x] Complete disposable-key end-to-end signing for Little Orbit and Big Orbit plus wrong-store-password, wrong-key-password, wrong-alias, wrong-certificate, redaction, independent metadata, and zero-residue cleanup checks on `.14`, with the final negative-verifier Docker caveat recorded above.
- [x] Confirm both people are off the app and disable `.182` schedules.
- [x] Create a fresh ordinary privacy-filtered encrypted backup and pass its restore drill.
- [x] Record source commit/image digests, migration head `0031`, privacy-safe table counts including feedback and feedback-operation rows, attachment aggregate digest, and every immutable-release size/hash.
- [x] Stage schema-0032-compatible source on `.182` for rollback without starting it.

## Exact transfer and cutover

- [x] Require an empty target database and attachment staging area.
- [x] Stop every source writer and direct-stream the complete logical database, frozen attachments, and immutable releases through pinned SSH without retaining the streams.
- [x] Match exact pre/post row counts, attachment digest, release sizes/hashes, roles/grants, and Alembic head `0032`.
- [x] Start target dependencies in order and pass readiness with `Host: lil-orb.pax-kun.com`.
- [x] Apply and inspect the NPM-only `DOCKER-USER` rule; reject another LAN source, expose no IPv6 listener, and preserve unrelated rules.
- [x] Change only Nginx Proxy Manager's upstream address from `.182` to `.14`, preserving HTTP port 8180 and the other proxy-host settings.
- [x] Verify the six public web routes, API readiness and release metadata, ClamAV, complete/ranged phone and Wear APK delivery, forwarded-client identity, and an unauthenticated WSS upgrade that reached the application and failed closed with `403`.
- [x] Confirm the same inode `3177412` in every named GPU consumer and an empty Ollama/VRAM state after cutover.
- [ ] Verify both existing sessions, authenticated WSS, Big Orbit enrollment/session behavior, SMTP, first-party notifications, and authorized attachment reads.
- [ ] Exercise Little Orbit GPU generation/embedding against live Scriptarr contention and prove no simultaneous Ollama, LocalAI, or NVENC process. Exact-file contention and idle-unload behavior passed before cutover, but the empty post-cutover state is not an active shared-workload test.
- [ ] Verify the public origin from an external cellular/WAN path after a separately authorized DNS correction. Three external nodes timed out for both Little Orbit and the unchanged `pax-kun.com` control; current WAN egress is `67.185.205.68` while DNS resolves to `67.185.206.35`. No DNS change was authorized or made during cutover.

## Required after cutover

- [x] Produce a fresh target encrypted backup and pass the local Tuesday-style restore drill at schema `0032` with the required privacy exclusions.
- [x] Rotate the four exposed child database roles through the host-locked command, independently reject every retired value, and pass a fresh post-rotation backup and restore drill.
- [ ] Reboot `.14` and reverify array/Docker ordering, Compose health, firewall persistence, schedules, GPU lock behavior, and public service health.
- [ ] Complete the deferred physical-device and two-person migration QA; current server and emulator evidence does not imply those observations.
- [ ] Establish and restore an encrypted off-host runtime copy. The Unraid parity-array backup remains local-only evidence until then.

Before `.14` accepts a write, rollback is an NPM upstream reversal plus restarting the frozen source. After a target write, `.182` is stale: the explicit reverse-stream command must restore current `.14` state into the separate fresh `little-orbit-rollback` project and match table, schema, attachment, and release evidence before that project can be considered for traffic. The old `little-orbit` project must never restart. Deleting its database or attachment volumes requires a separate explicit destructive approval; this implementation request is not that approval.
