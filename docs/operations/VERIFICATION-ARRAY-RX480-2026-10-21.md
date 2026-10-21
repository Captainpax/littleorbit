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
- Optional timezone-aware `RECOVERY_MAIL_NOT_BEFORE` filters delivery using the
  existing outbox `created_at`; earlier encrypted rows and retry/delivery state
  remain untouched. Unset normal behavior is preserved. Malformed/naive input
  refuses settings; this source guard is not deployed-worker acceptance.
- The last array overlay replaces all original services/networks and removes
  bootstrap/migration helpers. Its isolated worker/media holds import no app
  module, even when the old image ignores `WORKER_HOLD`; neither is app health.
- Stdin-only model preparation rejects unexpected commands, mounts, environment,
  device/privilege access, image-declared uncovered volumes and public ports.
  It emits no configuration/secrets and exposes no lifecycle operation.
- Actual-lock retention is armed before AMD work tasks. Unknown unload/device
  cleanup quarantines the same descriptor even if database retry persistence or
  cancellation replaces the original error. Only verified cleanup permits release.
- Candidate Compose/Dockerfile and the PHP host probe are not installed runtime
  acceptance. Container-only Mesa selection/build provenance and deployment
  review remain required. No host driver or interpreter was installed.

## Actual checks

| Check | Observed result |
|---|---|
| Prior API + AI pytest baseline on isolated local Python 3.13, before the optional mail guard | 262 passed, 49 skipped, 22 warnings |
| Full API + AI pytest after the optional mail guard, independently rerun locally | 273 passed, 49 skipped, 22 warnings; no production services contacted |
| Optional recovery-mail cutoff and related settings/cadence tests | 18 passed, including 11 new cutoff tests; SQLite and mocked SMTP only |
| Focused cutoff settings/delivery/test Ruff and mypy | Passed for all three changed Python files |
| Additional read-only array-admission stdlib suite | 16 passed |
| Nine-service profile and stdin preparation checks | 27 passed after integration, including six always-run pure contract checks and real local Compose 5.5.1 configuration parsing; no daemon |
| Independent real GPU-lock lease regression suites | 31 passed, one Windows symlink skip; CPU logic only |
| Ruff over API, AI and new admission scripts/tests | Passed |
| Ratcheted quality checker | Passed for 561 source files after the optional mail guard; baseline not enlarged |
| Documentation inventory and links | Passed for 134 owned Markdown files |
| CI-equivalent `mypy services` | Passed for 219 source files |
| PHP syntax through node2's existing PHP 8.4.21 | Passed for exact candidate bytes; server was not executed |
| Strict project-config mypy baseline comparison | 11 existing errors in eight unchanged files, reproduced on clean base; focused changed-source check is separate |
| Whitespace diff check | Passed |

The existing CI now also runs array admission and profile preparation suites.
Profile tests discover a local Compose CLI or accept an explicit
`ORBIT_TEST_COMPOSE_BINARY`; when it is unavailable, the six pure contract
checks still run and configuration-dependent checks are reported skipped.
The push
workflow builds/tests source only; it does not deploy the recovered host.

The recovery-mail addition is checked separately with an in-memory SQLite
selection and mocked SMTP, including an older backlog larger than the batch
limit, inclusive boundary, timezone normalization, future cutoff, ordinary
unset delivery, unchanged due/delivered guards and unchanged held ciphertext.
These tests contact neither SMTP nor a database server; they do not prove
production PostgreSQL, mailbox delivery or worker release.

Database integration skips reflect the absence of a separately isolated test
PostgreSQL URL; production databases were not used. Windows cannot exercise
Linux Unix-socket/DRM ownership or all symlink paths. Existing OpenAPI duplicate
operation-ID and dependency deprecation warnings remain visible; they were not
silenced or represented as new production acceptance.

## Remaining acceptance

Fresh coherent source semantics and copied-file verification, PostgreSQL/WAL
startup on a rollback-protected working copy, exact local image and Vulkan ICD
provenance, real RX480 tests for both models, host-probe lifecycle/census review,
target Compose/image/mount review and lifecycle controller, worker-hold release, firewall/private/public
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
