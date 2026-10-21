# Array/RX480 recovery implementation verification — 2026-10-21

Status: local implementation verified; restoration and hardware acceptance pending.

This record is not a service-online announcement, a new application release, or
a claim that real GPU inference passed. Source work began from main commit
`5136b74c9ce812cce3f50630a58cb5e89582c603`. No application data, private
inventory paths, passwords, backup identities or signing material are in Git.

## Implemented scope

- Read-only array admission binds exact paths, direct XFS backing, current
  quarantine, sealed size evidence and a 200 GiB runtime/full-growth budget plus
  at least 100 GiB residual space. It exposes no lifecycle operation.
- Explicit AMD ownership and inference checks require the pinned physical
  device, original model digests and actual generation/embedding offload.
  The normal NVIDIA profile remains the default.
- Recovery proof mode cannot pass using curated substitution. Normal AMD
  serving still retains safe, labeled degraded reserve coverage after rejecting
  unaccepted inference; CPU-only model output is never accepted as GPU output.
- Worker hold prevents mail, privacy, queue and scheduled tasks from starting.
- Actual-lock retention is armed before AMD work tasks. Unknown unload/device
  cleanup quarantines the same descriptor even if database retry persistence or
  cancellation replaces the original error. Only verified cleanup permits release.
- Candidate Compose/Dockerfile and the PHP host probe are not installed runtime
  acceptance. Container-only Mesa selection/build provenance and deployment
  review remain required. No host driver or interpreter was installed.

## Actual checks

| Check | Observed result |
|---|---|
| Full API + AI pytest suite on isolated local Python 3.13 | 262 passed, 49 skipped, 22 warnings |
| Additional read-only array-admission stdlib suite | 16 passed |
| Independent real GPU-lock lease regression suites | 31 passed, one Windows symlink skip; CPU logic only |
| Ruff over API, AI and new admission scripts/tests | Passed |
| Ratcheted quality checker | Passed for 557 source files; baseline not enlarged |
| Documentation inventory and links before this record | Passed for 133 owned Markdown files |
| PHP syntax through node2's existing PHP 8.4.21 | Passed for exact candidate bytes; server was not executed |
| Strict project-config mypy baseline comparison | 11 existing errors in eight unchanged files, reproduced on clean base; focused changed-source check is separate |
| Whitespace diff check | Passed |

The existing CI now also runs the CPU-only array-admission suite. Its push
workflow builds/tests source only; it does not deploy the recovered host.

Database integration skips reflect the absence of a separately isolated test
PostgreSQL URL; production databases were not used. Windows cannot exercise
Linux Unix-socket/DRM ownership or all symlink paths. Existing OpenAPI duplicate
operation-ID and dependency deprecation warnings remain visible; they were not
silenced or represented as new production acceptance.

## Remaining acceptance

Fresh coherent source semantics and copied-file verification, PostgreSQL/WAL
startup on a rollback-protected working copy, exact local image and Vulkan ICD
provenance, real RX480 tests for both models, host-probe lifecycle/census review,
array Compose/controller review, worker-hold release, firewall/private/public
API/auth/WSS/media/APK/TLS tests, restart, soak and autostart remain pending.
Original source, cache image, backups and failed evidence stay preserved.

## Markdown impact review

Every owned Markdown path was inventoried. README, ROADMAP, network/privacy
guides, deployment/backup runbooks, affected infrastructure/API/AI agent guides,
ADR 0049 and this verification record are affected and updated. Historical ADRs,
release/verification records and signing instructions remain historical and are
not rewritten. SHOWCASE, concept assets, Android/web/protocol guides, contributor
and community documents, security-reporting policy, and reviewed AI knowledge
have no changed UI, protocol, user-data use or editorial promise. Their content
is unchanged. Third-party/runtime-image license and package provenance remain a
build gate; this candidate adds no deployed host package.
