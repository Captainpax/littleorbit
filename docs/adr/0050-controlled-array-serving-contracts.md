# ADR 0050: Controlled direct-array serving contracts

Status: accepted design; local implementation only, native acceptance pending

October 29 gateway implementation correction: the recovered Caddy executable
retains the file capability `NET_BIND_SERVICE`. Its all-capabilities-dropped
private request failed before Caddy ran. Retain exactly that capability only for
the recovery gateway, with read-only root, all other capabilities dropped and
no-new-privileges unchanged. Reject a missing/extra gateway capability and any
capability addition to another role. Preserve the failed request and executable
metadata. Local tests do not authorize an in-place change to the frozen native
generation or establish successful gateway/public startup.

Date: 2026-10-22

October 29 clarification: private AMD protocol 2 preserves a missing busy sensor
as null/EBUSY only with stable, previously active kernel runtime suspension,
zero owners and known idle VRAM. It never treats this as active residency. The
bounded native helper also verifies peer UID and the admitted worker cgroup.
No public listener or worker host PID access follows from these checks.

## Context

ADR 0049 deliberately holds workers and does not publish a host port. Its
internal private network cannot deliver fresh SMTP, and disabled Docker NAT
cannot provide the context fetcher's outbound path. Recovered image-cache
availability, immutable build bases and complete transitive wheels are not yet
known. An original worker predating the mail cutoff and strict AMD guards
cannot be released by setting new environment variables that it may ignore.

## Decision

Keep inert preparation unchanged. A distinct last-file serving candidate uses
the same nine-role graph, image IDs, reviewed binds, numeric users and private
trust addresses. It releases only explicitly reviewed worker/media commands,
fixes approved per-role resources and requires one owned aggregate parent for
all nine CIDs plus the containerd/dockerd cohort. Model validation always emits
empty lifecycle permissions; sealed-reference requests are not boolean proof.

Use native, owned, narrow DNAT/FORWARD plus tuple-scoped egress SNAT without
enabling Docker's firewall/NAT flags. Preserve NPM's source IP through DNAT;
do not substitute an ordinary TCP relay that changes Caddy's immediate peer.
Only context-fetcher HTTPS/DNS and worker recovered SMTP/DNS gain egress.
Fresh native rule ownership, expiring DNS sets, actual namespaces and negative
network tests are mandatory, not supplied by this repository's pure model.

Credentialed SMTP must use certificate/hostname-verified STARTTLS before login;
missing/partial TLS credentials refuse before connecting. The existing optional
aware-UTC cutoff remains once-recorded and historical mail remains untouched.
The context fetcher ignores environment-derived proxies.

Build the changed worker only from a digest-bound, metadata-accepted Linux amd64
Python base and exact prebuilt, hash-locked wheels for the reviewed source and
every transitive dependency. No unversioned installer upgrade, network resolver,
source distribution, apt/APK install or implicit build dependency is permitted
inside that build. The checked-in null/empty manifest is intentionally unsealed
and fails closed. Do not invent upstream digests or wheel versions to complete
it. Other original images may be reused only after actual cache metadata and
content/entrypoint acceptance; unknown does not mean missing.
The base's actual entrypoint must be captured and admitted empty/null; the final
image explicitly clears it. A nonempty inherited wrapper is a refusal, not an
assumption that the official Python name implies safe entrypoint behavior.

## Consequences

- Normal cache/NVIDIA launchers, their firewall behavior and immutable history
  remain unchanged. This narrowly extends ADR 0049 only for reviewed serving.
- A 26 GiB parent, no swap and `min(8, fresh online CPUs)` cap contain combined
  daemon/application consumption; child CPU limits are ceilings, not promises.
  Fresh host headroom remains at least 8 GiB.
- CPU/config tests do not establish cold-state, database, source, secret, image,
  GPU, mailbox, public API/WSS/APK, controlled restart or soak acceptance.
- No application protocol, account, secret, APK, model, notification provider or
  production payload changes are authorized by this design.

## October 29 implementation observation

The later separately reviewed topology in ADR 0052 uses standard Docker IPv4
firewall management with owned isolation. Its deployed app parent is 26 GiB;
daemon/controllers have a separate 2 GiB parent. All nine services are public,
and the owner confirmed existing login/data. The native policy uses legacy
iptables time predicates for bounded DNS address leases; this host has no
admitted ipset/nft implementation. Rotating answers retain independent TTLs,
and the gateway has an NPM-only route inside its own network namespace so no
ingress SNAT or physical host route change is required.

Both original GPU model paths, verified SMTP AUTH without delivery, privacy
expiry, public authorization guards and the persisted nine-container restart
passed. A fresh 31-sample, 30-minute stability window and durable array-start/stop
hooks subsequently passed, including adoption without restarting current
processes. No node2 host reboot was performed. See the dated verification record;
this observation does not
retroactively seal the unused wheel candidate or relax any earlier refusal.
