# Array image staging and code-only recovery artifact — 2026-10-29

Status: original image availability, first artifact and private PG17 checks
passed. Physical GPU computation and a distinct typed idle producer were
observed; worker/probe integration and public acceptance remain pending. The
separate DMS copy disagreement remains held. No RAM fault is established.

## Verified scope

Harbor's real reboot and fresh stability prerequisite passed independently.
The shared array-backed daemon completed its empty-runtime transition with
standard IPv4 NAT. Eleven original image config IDs were imported without tags
or registry pulls, followed by the previously downloaded pinned Ollama image.
The resulting census was twelve approved images and zero application containers.
These observations do not establish database semantics or actual GPU offload.

Original image metadata identifies Python 3.12.11 and 52 installed distributions.
The recovered PG17 image uses numeric identity `999:999`. Preparation now uses
that user/socket group and the existing nested `pgdata`, preserving recovered
ownership and refusing stock initialization or an incorrect cluster path.

## Code-only artifact

`array_cached_overlay.py` creates a bounded recovery archive from an exact
already-installed base and frozen application source. It does not run a
resolver, installer, builder daemon or container. A first artifact was built
from 147 source files, with a flushed independent artifact hash. Native Linux
synthetic tests passed. No production data, migration or new dependency was
included. This was the build checkpoint; subsequent native results follow.

The archive preserves base DiffIDs and uses empty base-layer placeholders.
Its intended classic-cache import must reuse the exact existing layers and
refuse a miss. This behavior is informed by upstream loader code; actual import
on the target version remains a separate pending gate. Never fetch a replacement
base or treat an absent layer as an empty accepted layer. Verify the derived
config/rootfs, actual installed dependencies and code before allowing a worker.
The earlier wheel-based candidate remains unsealed; it was not fabricated as
a successful build or replaced with invented package receipts.

## Checks and limits

- Preparation, serving-contract and shared-resource tests: **54 passed**, no skips.
  The Compose CLI rendered synthetic configuration only.
- Code-only artifact tests: **7 passed** locally and **7 passed** on Linux.
  They cover deterministic config/layer construction, no base-payload copying,
  unchanged inputs, unsafe source paths, wrong base/platform/user/ABI/entrypoint,
  and schema/dependency drift refusal. They are not native import acceptance.
- Focused Ruff and strict mypy passed. Source limits passed for 576 files.
- A target Python 3.12 syntax prerequisite check refused the recovery host's
  Python 3.14 before source reading or execution. It remains failed/pending;
  Linux artifact tests on that host do not establish the target interpreter ABI.
- Database/source provenance, dependency behavior, managed workload admission,
  isolation, real RX480 generation/embeddings/unload, authenticated service
  acceptance, privacy/mail-cutoff behavior, restart/soak and autostart remain gates.
- A copy disagreement must stop that stage and preserve original/cold/failed
  copies. Zero parity/member read-error counters do not prove filesystem or
  memory health. Further filesystem or hardware diagnostics require their
  separately approved scope; never infer a repair permission from a log message.

Private host identities, application records, failure copies, hashes and recovery
receipts remain outside Git. No production release, commit or push is claimed.

## Scoped offline diagnostic follow-up

The user separately approved clean runtime closure and a temporary array/share
outage for one `xfs_repair -n /dev/md1p1` run. The exact daemon, supervisor and
managed containerd reached positive terminal states. The private runtime was
flushed and normally unmounted, its keeper positively closed, and only its exact
unmounted loop detached. An unused legacy libvirt image also needed a normal
unmount before Unraid could finish stopping the array; its file was preserved.
No forced/lazy unmount, repair, image recreation or additional check was used.

After Unraid entered Maintenance Mode, guards confirmed the managed target's
UUID/member identity, absence of disk/share mounts and loop holders, idle parity
and zero active member errors. The single read-only check completed with exit 0
and no structural inconsistencies reported. Its complete output, positive child
wait, unchanged unmounted state and closure receipts were preserved and
independently verified outside the repository. No repair was performed.

This metadata result does not validate file contents or RAM, erase earlier
kernel errors, or resolve the independent working-copy checksum disagreement.
At that checkpoint applications were off and disks/shares unmounted in Maintenance
Mode. A new hardware diagnostic, BIOS change or reboot requires its own reviewed
scope. Harbor's public ping still returned HTTP 200 with successful TLS
verification after this work; Harbor was not restarted.

## Subsequent private validation

The array resumed normally without a reboot. The distinct private runtime owns
only network-disabled PostgreSQL, a held worker and Ollama. The first worker
artifact imported using exact cached layers; target Python 3.12.11 compiled 139
source files and verified all 52 original distributions without application or
data/network access. An earlier host-interpreter refusal remains preserved.

Recovered PG17 reached schema 0032 after ordinary working-copy crash recovery,
with no initialization, migration or role reset. All recovered accounts remain;
an earlier exact-total-account assumption failed and stays failed. Socket trust
does not prove recovered passwords. The DMS disagreement remains separate.

Synthetic-only requests used the original generation and embedding models on
the physical RX480, with positive GPU residency/busy observations, followed by
empty model lists and return to baseline VRAM. A legacy reader cast unavailable
sensors to zero; its raw result and notices remain preserved rather than being
relabelled as integrated software acceptance.

The corrected native producer passed 17 synthetic checks, including kernel peer
credentials, and three actual double-sample read-only censuses. All found zero
DRM owners, baseline VRAM and previously active runtime suspension, preserving
busy as null/EBUSY. Fixture-order and closed-enumeration-FD failures remain
preserved. Local AI/protocol tests passed (53), plus focused Ruff, strict AI mypy,
AI evaluation and source limits. Worker revision, deployed broker, public/private
functional acceptance, restart/soak and autostart remain pending.

The distinct typed-probe worker artifact was built from the same frozen source
plus the reviewed GPU fix, then flushed, independently verified and delivered
to node2. It is not imported or running yet. A staging-path error remains
preserved separately; no accepted source payload was recopied or rehashed.

The complete nine-role private model rendered through the target's existing
Compose CLI with recovered private configuration. Review confirmed exact
images/users/ceilings, six disjoint internal networks, no host ports and both
workers held. Duplicate supplementary-GID merging was corrected explicitly;
an inactive-profile attempt and a byte-size string/type refusal remain failed.
A distinct saved-model review verified canonical byte strings and all actual
structure. This is configuration review, not controller or application startup
acceptance. No extra application container was created.

## Later private cohort and integrated worker proof

The distinct nine-role private generation imported the typed-probe worker and
created only the approved nine containers. Eight remained running privately;
gateway startup exited 255 with `exec /usr/bin/caddy: operation not permitted`.
Read-only inspection in the actual runtime mount namespace found only
`NET_BIND_SERVICE` in that binary's file-capability metadata. The failed request
dropped all capabilities. The gateway-only correction and refusal cases passed
42 local profile tests and focused Ruff; native correction remains pending.

The revised worker verified 147 source files, compiled 139 Python files and
matched all 52 original distributions on Python 3.12.11. Private TCP credential
proofs accepted the recovered API, worker and media passwords and rejected wrong
passwords. Read-only queries confirmed schema 0032 and preserved operational
account counts; no initialization, migration, reset or test email occurred.

The worker authenticated the root-owned schema-2 probe through its admitted
socket path. Synthetic Qwen generation produced 24 tokens with positive GPU
residency and 100% physical GPU busy; Nomic returned eight 768-dimensional
vectors with positive residency and 100% busy. Both used their original model
digests and verified unload before releasing the original lock inode. The
temporary broker exited cleanly. Unavailable transition observations were
excluded while observing the same request, not treated as success or replaced
with another request. Earlier failed proof stages and exact ordinary cleanup
receipts remain preserved separately.

The original aggregate parent limits were observed cleared after the first
private child startup. A distinct admission restored only the approved parent
limits after checking the exact enrolled child and full memory headroom; fresh
observations after later starts still showed the 26 GiB/8 CPU/no-swap bound.
The cause of that earlier change remains unestablished and needs lifecycle
coverage. Public access, working privacy expiry, worker/media serving release,
durable network/probe ownership, restart/soak and autostart are not accepted.

## Subsequent public recovery and controlled restart

Later October 29 observations supersede the earlier pending stage descriptions,
while every original failed record remains unchanged. All nine approved services
started with the gateway-only capability correction. The actual production
`post_inference` path passed Qwen generation and Nomic embeddings with their
original digests, physical RX480 residency and verified unload. A managed root
probe now authenticates the serving worker's exact container identity.

Working-copy privacy expiry removed 787 expired raw-location rows and left the
cold copy unchanged. Counts remained four recovered accounts and two couples;
these are operational aggregates, not a newly initialized database. Original
API/worker/media credentials passed TCP checks and wrong passwords were refused.
The single mail watermark remains durable. Certificate/hostname-verified SMTP
AUTH returned 235 without MAIL, RCPT, DATA, test email or credential rotation.

All five approved context sites passed TLS. A real unapproved TCP request
increased the owned context DROP counter; an isolated native kernel namespace
proved rule expiry without production relaxation. DNS answer rotation exposed
a mismatch between the host and worker resolvers. The corrected owner keeps
each observed address only through its own original TTL, including the worker's
actual resolver view. A known DNS timeout may retain still-valid leases but
never extends an expired address. Old failed owners and unexecuted candidates
remain preserved rather than relabeled successful.

The existing NPM route, certificate and hostname were unchanged. Source-preserving
DNAT and the gateway's NPM-only return route restored public HTTP 200 and valid
TLS for the website, API readiness and release metadata. Account and synthetic
attachment requests without authentication returned 401; a public unauthenticated
WSS upgrade returned 403. Both original signed APKs passed private 206 range,
length and checksum-header checks. ClamAV returned PONG and detected an in-memory
synthetic EICAR fixture without writing attachment data. The owner confirmed
existing-account login and relationship data in the real app.

One approved Little Orbit-only shutdown then closed ingress, normally stopped
the nine services, closed the broker, and positively closed the daemon and image
mount. The persisted startup controller reopened the same image and all nine
container IDs. It admitted fresh PG17/schema 0032, original account/couple counts,
scanner readiness and both actual GPU paths with unload before public ingress.
It retained a separate 64 GiB runtime reserve, full array growth/rollback/reserve
budget, the 26 GiB app and 2 GiB daemon parents, no swap and 8 GiB host headroom.
No host reboot, model download, migration, repair or extra container occurred.

A fresh 30-minute sampled native/public/TLS/Harbor observation window is running.
The durable boot-hook contract passed code/custody checks but autostart is still
held until that window and actual hook installation are independently accepted.
Human login confirmation does not imply a full paired-device WSS reconnect or
attachment editing test. Those broader physical-device checks remain distinct.

The first post-restart window later stopped on a DNS presentation-parser
refusal. That version did not retain the rejected input, so its exact line is
unknown; twelve fresh read-only queries subsequently returned clean records.
A reviewed successor treats the entire unparseable or zero-TTL observation as
unavailable, creates no fresh lease, preserves a diagnostic and prunes expired
addresses before applying rules. Strict CNAME/public-address checks remain in
force. It adopted only the network role; all nine application processes, the
daemon and the GPU broker remained unchanged. Its 32 native policy fixtures,
five actual context TLS peers and verified SMTP AUTH passed. A distinct fresh
stability window is running; the failed window remains failed.

The owner's foreground app then produced actual authenticated notification WSS
acceptance and profile HTTP 200 after restart. Both public original APK ranges
returned 206 over verified TLS with exact published length/hash headers. A real
non-NPM LAN connection attempt was denied and increased the owned DROP counter.
No complete APK copy/hash, test account, password reset or email was generated.

An autostart preflight initially compared same-named chains across all tables
and mistook Docker's NAT OUTPUT jump for filter ordering. The corrected check
selects the actual filter table; current INPUT/FORWARD/OUTPUT hooks were already
first. The original failed observer is preserved. No firewall change followed
that diagnostic correction, and the independent live-writer/rule comparison
passed. The durable hook contract also verified the explicit current-generation
adoption without restarting any application process.
