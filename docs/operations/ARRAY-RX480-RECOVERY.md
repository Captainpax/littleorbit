# Direct-array and RX480 recovery

Status: implementation in progress; not production or GPU acceptance.

See the [implementation verification record](VERIFICATION-ARRAY-RX480-2026-10-21.md)
for actual local tests, skips and remaining host/hardware gates.

This is a separately approved cache-loss recovery path. It does not weaken or
replace the normal cache/NVIDIA launcher. Harbor restoration on another host is
an independent workstream; this repository contains no Harbor credentials,
private recovery inventories, database files, attachment names, or receipts.

## Storage and source gates

- Admit only the exact direct array mount `/mnt/disk2` and its reviewed member;
  reject missing mounts, ROOTFS and user-share fall-through.
- Use `/mnt/disk2/little-orbit-recovery/{live,deploy,secrets,gpu-coordinator,rollback}`
  and a fresh 200 GiB runtime image at
  `/mnt/disk2/system/docker-little-orbit/docker.img`. Never boot the old image
  or the empty runtime accidentally created beneath `/mnt/cache` on ROOTFS.
- Budget full runtime growth, application/model allocations, staging and cold
  rollback together, with at least 100 GiB remaining. Receipt timestamps and
  available capacity must be fresh; plan for ongoing growth monitoring.
- Independently select the full coherent original PostgreSQL 17 state,
  attachments, original secrets, model manifests/blobs, immutable APKs and
  deployment revision. Preserve numeric ownership, modes, ACL/xattrs,
  hardlinks and sparsity; flush and independently verify copied files.
- Preserve the original read-only cache image, canonical map and all encrypted
  backups. Do not repeat an accepted whole-image hash. A historical inventory
  accepted for a different scope is only a candidate until separately reviewed.
- Cold rollback precedes ordinary PostgreSQL crash recovery on working copies.
  No initdb, schema migration, role/password reset, or guessed defaults.
  Privacy-filtered backup fallback requires an explicit data-loss decision and
  a coherent database/attachment pair, not two independently newest artifacts.

`infra/scripts/array-recovery.py` currently provides only `admit`, `validate`
and `quiet-compose`. Admission binds caller-reviewed digests, fresh target
observations and capacity; it intentionally returns pending semantic gates and
an empty set of services allowed to start. It never creates an image, mounts,
copies, enables Docker or starts a service. Quiet Compose is syntax-only and
suppresses expanded secret-bearing output. The target currently has no Python
interpreter; a separately reviewed existing-runtime controller remains required.
Do not install a host interpreter merely to bypass that execution gap.

The reviewed historical metadata selection contains 3,897 entries and 3,308
files, totaling 4.285 decimal GB across live state, deployment, secrets,
coordination and preservation-only tool candidates. These are hash-row
candidates, not fresh filesystem, PostgreSQL/WAL, model-graph or credential
acceptance. Private selected paths and fingerprints remain outside this repo.

## Mandatory AMD proof

The recovery target has an AMD RX480 with 8 GiB VRAM and the `amdgpu` driver.
That metadata alone does not prove inference compatibility. Keep the default
NVIDIA profile unchanged; explicit AMD mode must fail closed without its own
host and model proofs.

The narrowly evaluated backend candidate is Ollama 0.35.1 for Linux amd64,
with a reviewed Vulkan/Mesa ICD inside the container, not new host drivers.
The candidate is not yet a locally accepted production image. Preserve both
original model digests: Qwen generation and Nomic embeddings. Do not download
replacement models or try arbitrary ROCm architecture overrides after failure.

A stable single-link host GPU lock is held through the entire operation.
An unprivileged worker cannot infer host GPU idleness from its own process
namespace. A narrow root-owned Unix-socket probe must validate peer identity,
fresh nonce, exact PCI/render device and complete host DRM ownership census;
unknown or unavailable information blocks work. Do not grant worker hostPID,
privileged mode, a Docker socket or broad host `/proc` access.

`GPU_PROBE_BACKEND=amd-vulkan` requires offload checks for actual inference;
`GPU_RECOVERY_PROOF_MODE=true` is the separate strict acceptance phase and is
the recovery overlay default. In normal AMD serving, rejected inference may
still use the existing reviewed reserve/curated coverage, recorded as degraded,
never as GPU success. The proof phase cannot use that substitution to pass.
`WORKER_HOLD=true` blocks mail, queue, schedules and privacy tasks before they
start. Releasing that hold remains a separate stage decision.

For **both** generation and embeddings, synthetic-only tests must prove exact
model identity and actual RX480 residency. CPU assistance is allowed; CPU-only
or curated fallback is not a successful recovery test. An AMD inference call may
retain a model for at most 30 seconds while proving residency under the same
lock, then explicitly unload it and verify release. Unknown cleanup retains
the same lock descriptor for that process's lifetime. Process exit releases
the OS lock, but a new process must repeat the complete host-state check.

## Staged service acceptance

The eventual long-running allowlist is gateway, web, API, PostgreSQL, worker,
context fetcher, Ollama, media worker and ClamAV. An allowlist is not a start
command. Keep every unrelated container, plugin child and User Script disabled;
libvirt stays disabled. Verify this before deliberately enabling a new runtime.

Never issue a blanket Compose `up`: the original dependency graph can bootstrap
roles, initialize fresh storage or run migrations. A later reviewed array
overlay, exact local image IDs and `--no-deps --no-build --pull never` stage
controller are required before any lifecycle action. Workers remain held before
privacy maintenance, queue claims and schedules. Separately authorize ordinary
working-copy privacy-expiry maintenance before public traffic; preserve forensic
source bytes without exposing expired private state through the service.

Keep the gateway closed until schema, storage, model/GPU, private service and
firewall gates pass. Preserve the existing NPM-only upstream boundary to
`192.168.50.14:8180`, Caddy/API reserved addresses on `10.253.14.0/28`, public
hostname, certificate and unrelated routes. Prove authenticated API and WSS,
private attachment authorization/scanning, immutable APK identity/range delivery,
SMTP behavior without exposing credentials, and actual GPU operations. Require
one controlled Little Orbit-only restart and a healthy soak before autostart.

Stop a failed stage and preserve its evidence. A timeout is not permission to
replace a running job. Ask before reboot, hardware changes, data-loss fallback
or broader workload restoration. Local CPU tests and source review must never
be reported as host/GPU/public acceptance.
