# Array serving-contract implementation verification — 2026-10-22

Status: local code/config checks only; no build, host, hardware or public acceptance.

## Scope

Branch `codex/orbit-serving-contracts` starts at `717c978`. This change adds
verified credentialed SMTP STARTTLS, disables environment proxies in the fixed
context fetcher, and adds separate serving/resource/network/build-closure
contracts. The inert preparation overlay and native private recovery evidence
are unchanged. No commit, push, image build/download/import, Docker daemon query,
host change, lifecycle action, SMTP delivery or registry/model request was run.

The complete 134-file repository-owned Markdown inventory was read and reviewed
for impact. Historical ADRs/releases/verification, product protocol, visual
showcase, Android/Wear, signing and knowledge documents remain accurate as
historical or unchanged scope. Current README/ROADMAP, security/privacy, network,
infrastructure guidance, deployment/backup/recovery operations and inventory
were updated. ADR 0050 records the narrow new recovery design; no historical
verification is rewritten as current acceptance. Existing Mermaid source and
its labelled historical topology are unchanged; the distinct proposed recovery
flow is a table, not a regenerated production architecture image.

## Local results

- API and AI suites: **284 passed, 49 skipped**, with existing third-party
  deprecation and duplicate legacy OpenAPI-operation warnings. PostgreSQL-backed
  integration gates remain skipped without an explicit disposable test database.
- Array admission/preparation/serving/network/resource/build-closure tests:
  **72 passed**, including base-ABI/entrypoint negatives and a direct wrong-role
  egress-helper rejection. The real
  four-file Compose merge invokes only `config --no-env-resolution
  --no-path-resolution --format json` with synthetic values; it does not contact
  a daemon, load a real env file or start a container.
- Targeted SMTP/context/cutoff/link suite: **23 passed**. Synthetic TLS failures
  cannot reach authentication/send; plain no-auth development remains supported.
- API Ruff passed for the full service; focused new infrastructure Ruff passed.
  Full API/AI mypy passed for **222 source files**.
- Source size/complexity limits: passed for 572 source files; no ratchet exception
  was added.
- Documentation inventory/local links: passed for all **136 files**, including
  this record and ADR 0050. Whitespace diff checks passed.
- Markdownlint and hardware/browser rendering were not run; no local
  markdownlint binary was available, no package was downloaded, and no Mermaid
  source or application UI changed.

## Intentionally pending

The checked-in worker closure has null base/source/cache metadata and no wheels.
An exact base manifest/config, real Linux amd64/Python/pip metadata, immutable
source-to-project-wheel provenance and complete transitive dependency wheel
hashes/versions remain unsealed. All nine original local image IDs and image
ABI/entrypoint/volume acceptance require original-cache metadata; unknown is not
missing. No installer version, image digest or wheel version was invented.

Harbor boot and 30-minute proof must precede node2 activation. Native two-daemon
handoff/supervision, actual controller/limit membership, direct-array capacity,
existing PG17 schema/secrets, privacy/mail cutover, both RX480 model operations,
owned firewall/route/DNS expiry, positive/negative ingress/egress, authenticated
API/WSS/media/APK/range, controlled restart/soak and durable autostart are still
external gates. A serving request's reference shape or rendered model is not
genuine receipt validation and never grants execution authority.

## Final acceptance — October 29

Later native execution accepted the original image-cache identities and a
code-only recovery overlay on the original dependency base. The unused wheel
candidate above remains unsealed. Recovered PG17/schema 0032, original accounts
and credentials, both real RX480 model paths with unload, working-copy privacy
expiry, verified SMTP AUTH without sending mail and five approved context TLS
hosts passed. The owner confirmed existing login and relationship data; after
the controlled restart, the app established authenticated notification WSS.
Public APK ranges, unauthenticated guards, denied direct LAN ingress and bounded
DNS-expiry rules passed. No account creation, password reset or schema migration
was used.

The first post-restart window failed on a DNS observer refusal and stays failed.
A reviewed network-only successor retained all nine processes and discarded
unparseable resolver observations without renewing leases. The fresh window ran
from 11:41:21 AM through 12:11:22 PM PDT, with 31 healthy samples spanning 1,801
seconds. Every sample checked unchanged identities, storage/memory reserves and
valid public Little Orbit/Harbor TLS. The native autostart validator independently
checked the saved window before changing any boot hook.

Durable array-start/stop hooks passed installation and independent verification.
A duplicate installation retained one Docker daemon, one containerd and the same
nine container processes. The current generation was explicitly adopted; a
later boot restores sealed code and applies the existing storage, capacity,
database, GPU and isolation gates. SSH's existing CRLF INI setting was parsed as
enabled; an earlier strict line-ending observer failure is preserved. Stock
unrelated Docker/plugin autostarts and libvirt remain disabled. No node2 host
reboot was performed.

Final local checks passed: 83 array-contract tests, 22 transport/AMD-probe tests,
31 GPU/mail-cutoff tests, focused Ruff, strict mypy for the three affected source
files, source limits for 576 files, documentation inventory/links for 138 Markdown
files and whitespace checks. Markdownlint was unavailable and was not run.
Earlier failed stages, cold data and private recovery evidence remain preserved
outside Git. DMS's independent integrity hold and capacity-deferred AMZMC
transfers remain unresolved; they are not Little Orbit acceptance results.
