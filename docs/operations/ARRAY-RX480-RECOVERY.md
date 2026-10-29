# Direct-array and RX480 recovery

Shared DMS/Orbit scope follows [ADR 0052](../adr/0052-shared-array-docker-and-separate-budgets.md):
separate Orbit/daemon/DMS budgets and a separately reviewed standard Docker IPv4
NAT transition with owned isolation. The earlier disabled-firewall candidate is
historical; pure model output does not authorize a live transition.

Status: nine-service public recovery, owner login/data and authenticated WSS,
controlled restart, 30-minute stability window and durable boot hooks accepted.

## October 29 public restoration

The exact nine approved containers are serving through the unchanged NPM route
and valid public TLS. Recovered PG17/schema 0032 and original API/worker/media
credentials passed, including wrong-password rejection. The owner confirmed
existing login and relationship data. Both original model digests passed the
actual production `post_inference` path with RX480 residency and verified unload,
including a fresh proof after the controlled restart. The root peer broker is
bound to the current worker/container identities and original GPU lock inode.

Only the working copy lost expired raw-location rows; the forensic cold copy
remains unchanged. The original encrypted mail is protected by one durable
cutover watermark. SMTP AUTH passed with a verifying STARTTLS context and no
MAIL, RCPT or DATA commands. The five code-owned context hosts passed TLS.

Standard Docker firewall management remains unchanged. Owned legacy-iptables
chains admit only NPM's original destination tuple, without ingress SNAT. Caddy
has only the explicit NPM host return route inside its own network namespace;
no host route or default gateway changed. Context and SMTP destinations retain
each verified DNS address until its own TTL expires. Known DNS timeouts do not
renew leases; the kernel closes expired tuples. Actual unapproved context traffic
hit the owned DROP rule. An isolated native namespace proved accept-before and
deny-after kernel expiry without relaxing production rules.

The controlled restart closed public ingress first, normally stopped the nine
services, then closed the authenticated broker and owned daemon/image mount.
The persisted controller reopened the same image and all nine existing IDs,
admitted PG schema and scanner readiness, repeated both real GPU paths, and
published NPM ingress last. Separate array/runtime reserves, the 26 GiB app
parent, 2 GiB controller parent, no swap and 8 GiB host headroom remain enforced.
It does not initialize, migrate, download models, start another container, or
reboot the host. A fresh 31-sample, 30-minute window passed and was independently
validated on node2 before installing durable array-start/stop hooks.

The first window stopped on a DNS output-parser refusal. That failed window is
preserved. A separately reviewed network-only successor discarded unparseable
observations without creating or extending a lease, saved diagnostics, and
pruned expired addresses before rule generation. It retained the same nine
application processes, daemon, GPU broker and data. Five context TLS checks and
verified SMTP AUTH passed again; the new 30-minute window uses that owner.
The owner's real app subsequently reconnected authenticated notification WSS
and profile HTTP after the restart. Both public APK range deliveries and an
actual blocked direct-LAN attempt also passed.

The installed boot contract restores sealed controller code from flash and
starts only these nine existing containers after the array is ready. The
shutdown hook closes public ingress first and stops the owned services before
their daemon and image mount. A duplicate installation adopted the current
processes without restarting them. Stock unrelated Docker/plugin autostarts and
libvirt remain disabled. SSH's existing boot setting is enabled. No node2 host
reboot was performed; changed storage identities, insufficient reserves or
failed current attempts still refuse a later automatic start.

## Earlier private-phase evidence

October 29: Harbor's reboot and fresh stability prerequisite passed. The shared
daemon staged eleven recovered images plus the pinned Ollama image by exact ID,
with zero application containers. It was then cleanly stopped for the separately
approved offline disk1 read-only check; the private runtime mount and keeper
were positively closed, preserving the image. The array has since resumed
normally without a reboot. A distinct private runtime now contains only
PostgreSQL, a held worker and Ollama, without external networking.
The check reported no metadata inconsistencies, but the independent working-copy
content disagreement remains unresolved for the separate DMS database. Little
Orbit's previously accepted working/cold copies remain distinct. Its PG17
reached schema 0032 through ordinary crash recovery without initialization or
migration, preserving every recovered account. Private socket trust does not
prove passwords. The later private TCP proof accepted each original API, worker
and media credential and rejected deliberately incorrect passwords.

The latest private generation has eight running approved containers; the ninth,
Caddy, exited before serving traffic. Its preserved executable has
`cap_net_bind_service=ep`, while that generation's request dropped all
capabilities. A distinct correction retains only `NET_BIND_SERVICE` for the
gateway, preserves `cap_drop: [ALL]`, read-only root and no-new-privileges, and
rejects any capability addition to the other eight roles. This correction has
passed local profile/refusal tests but is not native startup acceptance. Do not
edit the frozen generation, remove executable metadata, broaden capabilities or
relabel its failed start.

The revised worker's target Python/source/dependency checks and private TCP
schema proof passed. Its schema-2 root-peer RPC then proved both original models
on the actual RX480, with strict live residency, physical busy/VRAM observations,
verified unload, the original lock inode and clean temporary broker shutdown.
Unavailable transition samples stayed unknown while the same inference request
continued; none counted as idle, residency or a successful sample. Earlier
configuration/path/observer failures and their ordinary cleanup remain recorded.
Both worker entrypoints remain held. Privacy expiry, durable probe lifecycle,
restricted ingress/egress, public functional checks, restart/soak and autostart
are still pending; do not release preparation by changing one hold flag.

The inspected PG17 Debian image defines `postgres` as `999:999`. The preparation
overlay uses that numeric identity and matching socket/tmp groups, preserving
the recovered files' original ownership. Its explicit `PGDATA` remains the
existing nested `/var/lib/postgresql/data/pgdata`; stock initialization and a
missing/wrong cluster are refused. Never infer an image user from the outer
host directory's group or create an empty replacement database.

A code-only recovery artifact can reuse the admitted original dependency base
without downloading or installing packages. Its frozen source, unchanged
schema/dependency inputs, new layer/config and actual classic-cache import
require separate proof. An empty base-layer placeholder is never a substitute
for a missing cache layer. Keep the older wheel candidate explicitly unsealed;
see the [October 29 verification record](VERIFICATION-ARRAY-IMAGE-STAGING-2026-10-29.md).

Stop on a source/cold/working content disagreement and preserve each candidate.
Inspect existing kernel logs before further activation. Completed parity and
zero member read-error counters do not establish filesystem or memory health.

`compose.array-private.yaml` is a distinct model-only validation candidate after
the base, RX480 and inert array files. It keeps worker/media entrypoints held,
adds the admitted aggregate parent and six disjoint internal networks, and
exposes only the render node to Ollama with cloud behavior disabled. It grants
no controller, firewall, create or startup authority. Render it with the explicit
`array-recovery-explicit-only` profile; an inactive profile can produce an empty
model. Compose byte-size fields can be canonical decimal strings, which must be
validated exactly before conversion, never confused with kernel observations.
The AMD supplementary group uses `!override` to prevent duplicate merged GIDs.
Never repair, replay, retry a failed copy or broaden diagnostic scope solely to
make a gate pass.

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

`compose.array-recovery.yaml`, applied last after the base and RX480 files,
replaces the complete service/network maps rather than hiding bootstrap helpers
behind profiles. It contains exactly nine explicit-only services, no build,
pull, dependencies, named volumes or host ports, and requires reviewed local
image IDs, numeric identities and resource limits. Both worker processes are
held by isolated standard-library Python without importing application code;
their disabled health checks are not application health. PostgreSQL bypasses
the stock initialization entrypoint and refuses missing PG17/control files.
Ollama models and ClamAV definitions stay read-only with no download egress or
automatic updater. This is a preparation profile, not a launch command.

`prepare-array-recovery-profile.py` accepts bounded rendered configuration on
stdin plus sealed admission/input contracts and emits only a sanitized result.
Do not save, tee or log a production expanded model: it may contain credentials.
Image-declared `Config.Volumes` must be inventoried and explicitly covered by
reviewed binds or bounded temporary filesystems; actual container mounts still
need independent inspection to exclude anonymous storage. Preparation grants
no lifecycle action, worker release, runtime-image creation or publication.

## Serving candidate, build closure and resources

`compose.array-serving.yaml` is a distinct, explicit-only last-file overlay:
base, RX480, inert array preparation, then serving. It is not a command to run
`up`, nor an admission receipt. It preserves exactly nine roles, reviewed image
IDs, existing bind access, numeric identities, capabilities/NNP, read-only model
and definition data, bounded logs and ephemeral directories. It adds no helper,
build, pull, dependency bootstrap, migration, published Docker port or automatic
restart. Only its reviewed worker/media commands replace the inert holds.

`array_serving_profile.validate_model` checks those exact deltas and replays
every inert model invariant against a comparison copy without changing the
actual input. Its typed admission *request* requires sealed references, not
all-true flags, and always returns no services/actions allowed to start. The
future native controller must independently consume the genuine receipts and
actual source/boot/PID/mount/network/cgroup state. In particular, the separately
approved Harbor boot plus 30-minute proof precedes any node2 activation. Do not
copy old readiness timestamps, treat a historical empty namespace listing as
current, or start dockerd under a containerd-only supervisor that rejects it.
The empty-runtime handoff and image staging have passed. A separately reviewed
managed-workload lifecycle is still required before creating or starting apps.

| Role | CPU ceiling | RAM MiB | PID ceiling |
|---|---:|---:|---:|
| Gateway | 0.25 | 256 | 64 |
| Web | 1 | 768 | 128 |
| API | 1 | 1024 | 256 |
| PostgreSQL | 2 | 4096 | 256 |
| Worker | 2 | 2048 | 256 |
| Context fetcher | 0.5 | 256 | 64 |
| Ollama | 4 | 8192 | 256 |
| Media worker | 2 | 2048 | 128 |
| ClamAV | 1 | 4096 | 128 |

Child ceilings total 22.25 GiB and 1,536 PIDs. Under ADR 0052, Orbit's own parent
caps its nine services at 26 GiB and `min(8, fresh online CPUs)`; daemon/controller
overhead and DMS have separate budgets. The earlier combined-parent candidate
is superseded. CPU child ceilings are caps rather than simultaneous reservations.
Reserve at least 8 GiB host RAM headroom after all remaining workload growth.
Prove actual CPU, memory and PID controllers, limits and membership. Keep host
swap disabled; enforce a zero swap limit where supported and record unavailable
accounting honestly elsewhere. Never invent a raw zero reading for an absent
controller. Fresh shared-budget admission must include current usage and remaining
growth without double-counting RSS. This host RAM contract does not prove the
RX480's separate 8 GiB VRAM behavior.

The narrow read-only original-cache metadata inventory and exact image imports
have passed. Cold live/deploy/secret state alone would not have established that
availability. Import establishes content and identity, not application compatibility.
Record exact local IDs, manifests/configs, architecture, users, entrypoints,
declared volumes and required libraries for all nine roles. Reuse an original
image only if genuinely present and compatible. The pre-cutoff worker requires
a controlled changed-source build even if its original image is available.

`infra/recovery/Worker.Dockerfile` is deliberately outside every Compose build
graph. `worker-closure.pending.json` contains null base/source/cache metadata
and no wheels; it cannot satisfy `array_worker_closure.py`. Before that wheel build,
seal the actual immutable base manifest/config and metadata, reviewed source
tree/commit and source-to-project-wheel provenance, plus exact filenames,
versions, sizes and hashes for both project wheels and the complete transitive
Linux amd64 Python dependency set. Hatchling/build-tool closure used to produce
the project wheels is a separate controlled preparation input, not a resolver
inside the final image. No upstream digest or transitive version is invented.
Provide the separately reviewed `worker-closure.json` and `wheelhouse` only
after their actual byte closure is accepted. They remain ignored private build
inputs, not a checked-in secret or fake lock.
The base's real `Config.Entrypoint` must be explicitly admitted as empty/null;
it is never inferred from an image name. A nonempty base entrypoint refuses this
candidate rather than silently running a wrapper. The final Dockerfile also
clears inherited entrypoint state explicitly and selects its own worker command.

The final build runs with no network for its install step, `--no-index`,
`--only-binary`, `--no-deps`, `--require-hashes` and `pip check`; there is no pip
upgrade, source-distribution build, apt/APK or arbitrary model download. The
external reviewed build owner must also disable frontend/base pulls, admit the
exact local base and preserve build/output evidence. This scaffold is not build
authorization and no build was run by local CPU tests. Old API/context/media
images are not silently promoted to the changed worker image or vice versa.

Credentialed SMTP now requires verified STARTTLS, complete credentials and the
privately recovered endpoint/port; there is no implicit-TLS/465 fallback. TLS
failure precedes login and send. Keep the original mail cutoff once-recorded at
cutover, not startup-now. Plain unauthenticated local Mailpit remains only a
development path. The context fetcher ignores environment proxies while
retaining fixed URLs, verified HTTPS, no redirects and body/DNS bounds.

The pure `array_serving_network.py` policy chooses native owned DNAT/FORWARD
plus exact outbound SNAT while all Docker firewall/NAT flags remain false.
The [network contract](../NETWORK-FLOW.md#explicit-recovery-serving-candidate)
and [ADR 0050](../adr/0050-controlled-array-serving-contracts.md) fix the two
egress bridges and NPM source-preserving ingress. Before installation, prove
fresh routes/interface/forwarding state, exact native firewall/ipset/ip/nsenter
carriers, chain/set noncollision and ownership, actual CID/IP/netns membership,
DNS/SMTP provenance and kernel lease expiry. No whole firewall restore or
unrelated rule change is permitted. Prove NPM-only ingress, denied other-LAN
and direct-container access, the `.2/.3` trust pair, authenticated WSS/ranges,
allowed context/SMTP/DNS and denied model/alternate/private egress. No network
rules, callbacks, periodic renewer or host controller are installed by these
pure modules; failed native capability or endpoint discovery remains a blocker.

Local verification commands (synthetic inputs and Compose `config` only):

```text
python -m unittest discover -s infra/scripts/tests -p "test_array_serving*.py"
python -m unittest discover -s infra/scripts/tests -p "test_array_worker_closure.py"
python -m pytest services/api/tests/test_mail_transport.py services/api/tests/test_public_context_transport.py services/api/tests/test_recovery_mail_cutoff.py
python infra/scripts/check_docs.py
python infra/scripts/check_quality.py
```

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

The backend candidate is the official Linux amd64 image
`ollama/ollama:0.35.1@sha256:17e945f1aa6e505707eeb621e3f36847d0a4a063d4778f7007645acccfb8bd4f`.
An independently verified, download-only static inspection found existing Mesa
`25.2.8-0ubuntu0.24.04.4`, the Vulkan backend, and the Radeon ICD at
`/usr/share/vulkan/icd.d/radeon_icd.json` (SHA-256
`bc0e4f88754ce48b429c05fc8c691438c5f04a4170d482c925bc5998159db299`).
Both AMD overlays select that exact ICD; Lavapipe also exists in the image and
must not be selected as a GPU substitute. The RX480 overlay no longer builds or
apt-installs Mesa. `OllamaRx480.Dockerfile` is retained as a non-default historical
candidate, not an instruction to build or install host drivers.

Static image contents are not loader, device or inference acceptance. The last
array overlay still requires a separately admitted exact local image ID matching
this manifest and its config; changing a Compose file grants no pull or start.
Preserve both original model digests: Qwen generation and Nomic embeddings. Do
not download replacement models or try arbitrary ROCm architecture overrides
after failure.

A stable single-link host GPU lock is held through the entire operation.
An unprivileged worker cannot infer host GPU idleness from its own process
namespace. The client authenticates the root-owned Unix-socket server using
Linux `SO_PEERCRED`; restrictive root/GID2000 permissions limit callers. The
schema-2 PHP server also verifies kernel peer UID and the exact admitted worker
cgroup through a bounded native helper. Its pinned configuration, boot identity,
fresh nonce, exact PCI/render device and complete
host DRM ownership census provide the ownership proof;
unknown or unavailable information blocks work. Do not grant worker hostPID,
privileged mode, a Docker socket or broad host `/proc` access.

Protocol 2 preserves an unavailable busy counter as `null` with `EBUSY`, never
zero. Idle additionally requires two matching kernel runtime-PM samples, prior
positive active time, zero DRM owners and known VRAM at/below baseline. An
active, transitioning, uninitialized or otherwise unreadable device cannot use
that exception. Residency requires active hardware, a numeric counter, positive
VRAM and only admitted Ollama owners. Keep the descriptor directory open while
inspecting the probe's own descriptors; a closed enumeration FD must not mimic
an unreadable persistent FD. Worker/broker integration remains a separate gate
from the native read-only producer test.

`GPU_PROBE_BACKEND=amd-vulkan` requires offload checks for actual inference;
`GPU_RECOVERY_PROOF_MODE=true` is the separate strict acceptance phase and is
the recovery overlay default. In normal AMD serving, rejected inference may
still use the existing reviewed reserve/curated coverage, recorded as degraded,
never as GPU success. The proof phase cannot use that substitution to pass.
`WORKER_HOLD=true` blocks mail, queue, schedules and privacy tasks before they
start. Releasing that hold remains a separate stage decision.

Before releasing the application worker, set its internal
`RECOVERY_MAIL_NOT_BEFORE` to the separately recorded cutover instant in an
explicit timezone-aware ISO 8601 form. This is an opt-in delivery filter, not a
database migration: only due, undelivered rows whose existing `created_at` is at
or after that instant are eligible. Earlier ciphertext, attempts, retry times
and delivery status stay untouched and unsent; do not decrypt, replay, delete,
retimestamp or reset the backlog to make admission pass. The boundary is
inclusive and normalized to UTC; invalid, empty or timezone-naive values refuse
settings/startup. A future boundary deliberately holds all earlier rows.
Keep the exact boundary across worker recreation; do not derive it from each
process's startup time or remove it while the preserved backlog remains.

The optional setting is unset in normal deployments, preserving their existing
delivery behavior. It grants no worker release by itself, creates no accounts,
and requests no password reset or automatic probe email. Verify fresh delivery
only through a separately admitted existing-user request; keep every original
account and credential intact. Confirm that the controlled build actually
contains this guard before releasing a recovered worker; old images may ignore
unknown environment settings.

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
roles, initialize fresh storage or run migrations. The array overlay and model
preparation validator now exist, but exact local image contents and a separately
reviewed `--no-deps --no-build --pull never` lifecycle controller are still
required before any start. Workers remain held before
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
