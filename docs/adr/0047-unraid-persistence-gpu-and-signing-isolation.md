# ADR 0047: Unraid persistence, shared GPU arbitration, and isolated signing

Status: accepted

Date: 2026-09-26

## Context

Little Orbit's production stack previously ran on a Windows host at
`192.168.50.182`. The Unraid server at `192.168.50.14` has the durable cache
pool, parity array, and RTX 4060 needed for the application, but the GPU is
also used by Scriptarr. Moving the stack must preserve every production row,
private attachment, active session, secret, and immutable APK without turning
the migration into a second privacy-bypassing backup. Android signing also
needs a repeatable Linux path without exposing signing material to production
services.

## Decision

Production uses the ordered Compose files `compose.yaml`, `compose.gpu.yaml`,
and `compose.unraid.yaml`. Only `192.168.50.14:8180` is published. Nginx Proxy
Manager remains at `192.168.50.6`; an idempotent `DOCKER-USER` chain admits
only that source for the original destination and port. The private Caddy/API
link uses `10.253.14.0/28` because the target already owns
`172.30.0.0/16`. Caddy and FastAPI retain fixed peer addresses, and FastAPI
derives its allowed public host from `PUBLIC_BASE_URL`.

Mutable live state uses direct cache-pool paths under
`/mnt/cache/little-orbit-live`. Encrypted, privacy-filtered backup pairs use
the array-only `/mnt/user/little-orbit-backups` share. PostgreSQL and
attachments are excluded from generic appdata snapshots. Source, runtime
secrets, shared GPU coordination, and signing material use separate
non-exported cache paths with least-privilege ownership. Runtime recovery is
therefore local to this server at first; an off-host encrypted copy remains an
explicit open reliability risk.

The one-time move is application-cold. Writers stop while a complete logical
PostgreSQL dump streams over host-key-pinned SSH directly into an empty target
database. Frozen attachments stream to verified staging and are promoted
atomically. Published release files are transferred separately and compared
by relative-path SHA-256. The migration tool has no archive-output option, so
it cannot retain a full private dump. Ordinary backups continue to omit raw
coordinates, device-health snapshots, attributable feedback, feedback
operations, and anonymous raw reviews.

Every GPU consumer opens the same stable inode at
`/mnt/cache/gpu-coordinator/gpu.lock`, exposed in containers as
`/run/gpu-coordinator/gpu.lock`, and takes an advisory exclusive lock before
loading a model or starting NVENC. The inode is never replaced. Little Orbit
queues content-free job metadata before contention, takes the host GPU lock
before claiming an AI run, fences leases with random tokens, and retries one
ordered job per six-hour slot. It keeps the lock through generation and
embedding, requests immediate Ollama unload, verifies VRAM is clear, and then
releases it. Scriptarr Oracle holds the same lock while LocalAI is resident
and unloads after 900 idle seconds; Raven holds it for each NVENC process.
Crashes must not permit a new consumer until both the advisory lock and actual
GPU process state are clear.

Little Orbit planning first becomes eligible Saturday at 01:00 and weekly
generation Sunday at 03:00 in `America/Los_Angeles`. Work stays persistently
ordered and may spill into weekday six-hour slots. A successful generation
creates and embeds fourteen days of safe coverage, so the hourly worker never
loads Ollama merely to repair a midweek gap. The five-account learning gate
and the prohibition on relationship data entering AI do not change.
The 01:00/03:00 eligibility times and fourteen-day horizon supersede only the
09:00 schedule and seven-day operational horizon in
[ADR 0045](0045-themed-retrieval-grounded-weekly-quizzes.md); its editorial,
retrieval, reserve, and semantic-safety decisions remain accepted.

Android builds and signing are separate one-shot containers outside
production Compose. A digest-pinned builder emits unsigned candidates. A
network-disabled signer has a read-only root, no Docker socket, dropped
capabilities, and a tmpfs work area. Separately encrypted Little Orbit and Big
Orbit bundles are decrypted only beneath `/dev/shm/little-orbit-signing`;
passwords travel through files, and cleanup is mandatory. Package, independent
phone/Wear version codes, byte counts, hashes, features, and pinned signer
identities are checked before manifest creation. Publication remains a
separate explicit action after static and physical-device checks.

## Consequences

- Unraid mover activity cannot relocate a live PostgreSQL directory, while
  parity storage still receives only encrypted, privacy-filtered archives.
- Nginx Proxy Manager changes only its upstream address; public DNS and TLS do
  not change.
- GPU contention delays AI or video work without preemption, duplicate model
  claims, or a false failed-run record.
- The shared lock coordinates cooperative consumers, so every new GPU tool
  must adopt the same inode, group, stale-process check, and bounded runtime.
- Production containers never receive Android private keys or signer
  passwords, and previously published APK bytes are never rebuilt.
- The old host remains a rollback source until target validation succeeds.
  Once the target accepts writes, rollback requires a fresh reverse stream;
  starting stale source state is forbidden.
- Loss of the Unraid server can currently remove both live state and its local
  backup history. Off-host encrypted recovery remains required work.
