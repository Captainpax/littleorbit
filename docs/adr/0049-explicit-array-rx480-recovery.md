# ADR 0049: Explicit direct-array and RX480 recovery

Status: accepted design; implementation and production acceptance pending

Date: 2026-10-21

## Context

The former cache device is unavailable and preserved read-only. A recovered
image and existing encrypted backups must not be replaced by an empty runtime.
The replacement GPU is an 8 GiB AMD RX480, so NVIDIA-only process checks cannot
establish safe ownership or inference. Restoring unrelated workloads would
expand the incident scope.

## Decision

Add an explicit Little Orbit-only recovery path with direct-array backing,
fixed separate paths, a fresh 200 GiB runtime budget, cold rollback and at
least 100 GiB residual reserve. Admit authentic source/schema/model/secret
provenance before lifecycle operations. Do not weaken original mount checks or
automatically run bootstrap, initdb, migrations or privacy-filtered fallback.

Add strict AMD/Vulkan mode without changing normal NVIDIA behavior. Require
actual GPU generation and embedding with original model digests. CPU assistance
is permitted; CPU-only or curated fallback cannot satisfy recovery. A narrow
host ownership probe and stable lock replace neither one another nor actual
per-call residency proof. Keep the worker unprivileged and held before queue,
schedule and privacy-maintenance mutation until separately admitted.

This supersedes only ADR 0047's cache-path/NVIDIA assumptions for this explicit
recovery profile. Its privacy, network, immutable-release, locking, signing and
backup requirements remain. Source evidence and existing backup history remain
preserved; no application protocol or Android artifact changes are implied.

## Consequences

- Storage admission, GPU source code, local tests, and runtime acceptance are
  distinct stages. Missing evidence blocks the relevant stage.
- Existing launchers remain fail-closed on missing cache mounts; the recovery
  path never manufactures cache-looking ROOTFS directories.
- Actual RX480 compatibility remains a hardware gate; failed proof does not
  authorize CPU fallback, random backend versions or host driver changes.
- Working-copy crash recovery and ordinary privacy expiry need explicit stage
  control before public traffic. Forensic source data is never served directly.
- Full operations and rollout gates are in the
  [recovery runbook](../operations/ARRAY-RX480-RECOVERY.md).
