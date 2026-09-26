# Unraid migration verification record — 2026-09-26

## Scope and current state

This record covers preparation to move Little Orbit from the Windows host at `192.168.50.182` to Unraid at `192.168.50.14`, share the target RTX 4060 cooperatively with Scriptarr, and make `.14` the isolated Android build/signing host.

As of this record, source implementation and read-only target preflight have begun. The production database and attachments have **not** been streamed, migration `0032` has **not** been applied to production, Nginx Proxy Manager still requires an explicit upstream cutover, and no `.182` database or attachment volume has been deleted. Source and target runtime claims remain pending until the evidence below is completed.

## Implemented in source

- `infra/compose.unraid.yaml` defines direct Unraid bind-backed state, the fixed `10.253.14.0/28` private gateway link, and the shared GPU coordinator mount.
- `infra/scripts/unraid-stack.sh` fixes production Compose order to base, GPU, then Unraid.
- The Unraid bootstrap, firewall, User Scripts dispatcher, backup, restore-drill, and operations runner use fixed paths and operation kinds. Only the five-minute pending runner may return successful `already_running`; backup and drill collisions wait boundedly or fail.
- `infra/scripts/direct_migration.py` accepts only the fixed `.182`/`.14` pair and SSH port 23, requires pinned host-key input plus direction-specific confirmation, and has no archive output. Forward mode requires the protected backup identity; rollback rejects it, preserves `.182` secrets/old volumes, and restores into the fresh `little-orbit-rollback` project. Both directions stop exact writers, reject running AI claims, use single-transaction database restore, verify sibling-staged attachments/releases, and emit matching content-free source/destination inventories before whole-tree promotion.
- Migration `0032` and the content-free AI work queue implement persistent scheduling, lease fencing, and shared-GPU acquisition before an AI run claim.
- The Android release directory separates a clean unsigned builder from a network-disabled one-shot signer, keeps secret plaintext in tmpfs, and verifies product policy before manifest output.
- ADR 0047 records Unraid persistence, exact streaming, cooperative GPU arbitration, local-only recovery limits, and signing isolation.

These bullets describe repository state, not a successful live deployment.

## Local verification completed

The following checks passed before this record was written:

| Check | Result |
|---|---|
| `python -m pytest infra/scripts/tests/test_direct_migration.py -q` | 30 passed |
| Ruff on the direct-migration command and tests | Passed |
| Strict mypy on the direct-migration command and tests | Passed |
| Ordered base/GPU/Unraid `docker compose config` with target values | Rendered successfully |
| Rendered published ports | Gateway only, `192.168.50.14:8180` |
| Rendered live PostgreSQL path | `/mnt/cache/little-orbit-live/postgres` |
| Rendered GPU lock path | `/mnt/cache/gpu-coordinator/gpu.lock` |
| Rendered gateway link | `10.253.14.0/28`, Caddy `.2`, API `.3`, trusted peer `.2` |
| `python infra/scripts/check_docs.py` | 130 repository-owned Markdown files inventoried; local links valid |
| `npx --yes markdownlint-cli2 "**/*.md"` | 0 issues |
| Mermaid CLI 12.0.0 render of `docs/NETWORK-FLOW.md` | All 27 diagrams rendered successfully |

This evidence does not cover the full API/AI, web, Android, Scriptarr, backup/restore, or signing suites. Those remain required below.

## Read-only `.14` preflight evidence

The authenticated Unraid dashboard and terminal showed:

- Unraid 7.3.1, array started, parity reported valid, and no active BTRFS operation at inspection time.
- Approximately 542 GB free on cache and 201 GB free through the array-backed user share at the latest CLI preflight. Disk 1 was about 90% used and disk 2 about 88% used, so capacity and retention must be rechecked immediately before transfer.
- Docker Compose 2.40.3, with `jq`, `flock`, and `git` available on the host.
- No host `age` or Python 3 binary. The bootstrap therefore installs a checksum-pinned `age` binary, while migration Python executes from the source or application container rather than relying on host Python.
- The route table already assigns `172.30.0.0/16` to `pterodactyl0`; this rejects the earlier `172.30.14.0/28` proposal. `10.253.14.0/28` was not present in the observed route table and is the configured replacement, subject to a final collision check.
- The current Scriptarr Oracle, Raven, Moon, Warden, and Sage containers were running and healthy. Older recovery-tagged Portal, Vault, MySQL, and Warden containers remain exited. Oracle's LocalAI process held about 4.9 GiB of VRAM at inspection time, so the lock-aware build and 900-second idle unload remain required before Little Orbit GPU work is enabled.

No terminal output containing a secret, row value, attachment name, signing password, or precise location was collected for this record.

## Required before source freeze

- [ ] Recheck the static/DHCP reservation, SSH port 23 host key, temporary migration key, free capacity, NVIDIA runtime, port 8180, IPv6 listeners, and `10.253.14.0/28` availability.
- [ ] Build and migrate an isolated target project with synthetic state; pre-pull the pinned Ollama models and refresh ClamAV.
- [ ] Deploy and pass Scriptarr Oracle/Raven tests for lock contention, 900-second idle unload, queued NVENC, crash/reboot recovery, and graceful fallback.
- [ ] Run Little Orbit API/AI tests, Ruff, mypy, web checks/tests, Android unit/lint tasks, Compose checks, backup/restore tests, and signing tests. Documentation inventory, local-link, Markdown-lint, and Mermaid-render checks are recorded above.
- [ ] Verify Pacific daylight-saving boundaries, ordered six-hour retry persistence, contention before `AiRun` claim, stale-lease fencing, administrator AI queueing, fourteen-day coverage, and timeout/OOM handling.
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
- [ ] Run wrong-password, wrong-alias, wrong-certificate, no-network, redaction, tmpfs cleanup, independent phone/Wear metadata, historical-APK immutability, and disposable-signer checks. Do not create a production-signed APK with an existing version code.
- [ ] Keep the original `.182` signer files until multiple disposable `.14` signer restore checks pass.
- [ ] Establish and restore an encrypted off-host runtime copy. The Unraid parity-array backup remains local-only evidence until then.

Before `.14` accepts a write, rollback is an NPM upstream reversal plus restarting the frozen source. After a target write, `.182` is stale: the explicit reverse-stream command must restore current `.14` state into the separate fresh `little-orbit-rollback` project and match table, schema, attachment, and release evidence before that project can be considered for traffic. The old `little-orbit` project must never restart. Deleting its database or attachment volumes requires a separate explicit destructive approval; this implementation request is not that approval.
