# ADR 0052: Shared array Docker and separate workload budgets

Status: approved scope; daemon and original-image staging verified; applications pending.

Date: 2026-10-28

## Context and decision

The user approved Pterodactyl DMS and Little Orbit on the same node. ADR 0050's
disabled-Docker-firewall candidate and combined daemon/Orbit parent cannot
describe that shared runtime. Retain the accepted runtime backing and Orbit's
nine-service allowlist. No unrelated service, VPN, upgrade or data-loss fallback
is approved by this decision.

After Harbor's real reboot and fresh stability acceptance, review one
daemon-only transition while applications remain off. Enable standard Docker
IPv4 NAT/port management with owned isolation. Preserve host forwarding intent,
unrelated rules and physical networking. Never flush global rules. Inspect the
actual daemon/rules and retain rollback; pure model validation grants no action.

Keep Orbit's nine containers under their own 26 GiB parent with CPU cap
`min(8, online CPUs)` and approved per-role limits. Budget shared daemon overhead
and DMS separately. Fresh admission reserves remaining growth in all budgets plus
at least 8 GiB host headroom without double-counting resident bytes. Keep the
100 GiB disk reserve, runtime growth and protected copies. New game requests
that do not fit queue rather than overcommit or silently relocate.

Host swap stays disabled. Enforce zero swap limit where supported. Where the
kernel lacks accounting, record it unavailable and prove no host swap; never
manufacture `memory.swap.max=0`. Unknown capability/usage refuses. A separate
native observer must join actual cgroups, identities, raw values, boot and time.

Keep Orbit's private addresses, NPM-only ingress, bounded context HTTPS/worker
STARTTLS egress and no Ollama/model egress. DMS uses a separate network and
resource contract. Keep libvirt/unrelated autostarts held. Only an admitted
workload generation becomes a durable boot allowlist.

## Current evidence and consequences

V1 validators and ADR 0050 remain historical candidate evidence. Their results
are not shared-runtime acceptance. New `array_shared_resources.py` checks
freshness, separate reservations, remaining RAM, CPU and honest swap capability.
Thirteen synthetic cases and focused Ruff pass; it has no host or runtime
control methods. Existing serving/SMTP/context/cutoff focused suites pass 45
tests. On October 29, Harbor passed its real reboot/fresh stability gate and
the shared daemon passed its empty-runtime transition with standard IPv4 NAT.
Eleven original images were imported by exact config ID with no tags, pulls or
application containers. This establishes image availability, not compatibility
or application acceptance. An image-only controller must be replaced through a
reviewed lifecycle before any application can be created or started.

Original image metadata identifies PostgreSQL's runtime user as `999:999`;
the recovered outer directory's group is not the image identity. The preparation
model now uses that image group for its user and socket/tmp directories, while
preserving recovered ownership and the existing nested `pgdata` directory.
It still bypasses stock initialization and refuses a missing PG17 cluster.

Mixed-controller, worker closure, native network, real RX480, service,
restart/soak and reboot acceptance remain pending. Restore the existing release
before feature migration. Accounts, data, APKs and API contracts are unchanged.

Later on October 29, the empty staging runtime and its private mount were
positively closed for a separately approved offline disk1 read-only check. It
reported no metadata inconsistencies and made no repairs. The independent
working-copy content disagreement remains an activation hold; node2 is in
Maintenance Mode, with all staged images and prior evidence preserved. This
does not alter the separate resource budgets or grant further diagnostic scope.

The array subsequently resumed without reboot. A distinct private runtime now
owns only recovered PG17, a held worker and Ollama. Schema 0032, ordinary recovery,
first worker cache/ABI checks and physical GPU computation were observed. DMS's
disagreement remains held separately; no memory fault or need for BIOS changes
has been established. Worker/probe integration, nine-role networking, functional
publication and durable serving startup remain pending with budgets unchanged.

The later nine-role private generation has eight running containers and a failed,
stopped gateway. The revised worker, recovered private TCP credentials and actual
worker/probe generation/embedding/unload proofs passed. A gateway-only file
capability correction is locally tested, not deployed. Privacy expiry, public
networking, serving lifecycle, restart/soak and autostart remain separate gates;
DMS's integrity hold and every storage/resource reserve remain unchanged.

The subsequent October 29 serving generation admitted the gateway capability
correction, separate worker/media serving entrypoints, authenticated managed GPU
probe, working privacy expiry and bounded context/SMTP networking. The owner
confirmed existing login and relationship data through the unchanged public
hostname. Its normal shutdown and persisted restart preserved all nine IDs,
images, data and separate budgets. Fresh PG/schema/scanner and both original GPU
paths passed before ingress returned. Stability sampling and durable autostart
are still pending; the DMS integrity hold and deferred transfers are unchanged.

The subsequent network-only revision retained the same nine processes through
a successful 31-sample, 30-minute stability window. Its durable array-start/stop
hooks were installed and independently verified, including duplicate installation
without restarting services. SSH remains enabled for boot; no node2 host reboot
was performed. DMS remains off under its integrity hold and transfers remain
deferred. This later acceptance does not reclassify any earlier failed stage.
