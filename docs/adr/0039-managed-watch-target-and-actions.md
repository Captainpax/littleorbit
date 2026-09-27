# ADR 0039: One managed watch and credential-free actions

- Status: accepted
- Date: 2026-09-19
- Extends: ADR 0012 and ADR 0014

## Context

The 1.0 watch companion was a passive cache receiver. Data Layer records were relationship-scoped, but they were broadcast to every paired Wear node and the app had no single place to manage watch privacy, versions, repair, or removal. Adding watch-originated Smooches creates a mutation boundary: a disconnected watch needs a short retry window, but it must never receive an account session or preserve an action across unpairing or watch replacement.

## Decision

Phone 1.1.0 explicitly selects one managed Wear node. App-private state records its Data Layer node ID, a monotonic watch generation, content switches, update-alert choice, default destination, and content-free version/status metadata. All active display, profile, and configuration records carry the target node ID and watch generation. A non-target watch that observes a newer generation clears its cache. Switching or removing a watch advances the generation; the old target receives a durable purge before it can accept another active record.

The watch receives no account token. A Smooch request contains one approved emoji, a UUID operation ID, creation time, opaque relationship identity/generation, watch generation, and protocol version. The watch keeps at most five requests in Android Keystore-backed AES-GCM storage for at most 15 minutes. The phone accepts a request only from the selected node and only when every generation, current relationship, preference, emoji, UUID, and expiry check passes. The phone then takes ownership in its existing encrypted idempotent outbox and acknowledges the watch. Sign-out, unpair, relationship expiry, watch switching, preference revocation, and private removal clear the applicable queue.

Update discovery remains metadata-only. Downloading APK bytes, pairing, install, reinstall, or removal always begins with an explicit person action. Private removal advances the target barrier, clears watch-originated queued actions, uninstalls the fixed Little Orbit package from the confirmed watch, forgets the phone's local ADB identity, and instructs the person to revoke wireless debugging on the watch.

## Consequences

Only one watch receives current relationship content. Multi-watch support would require a separately reviewed set of per-target generations and delivery ownership rules. A 1.1.0 phone intentionally retires legacy global watch payloads; an older companion becomes unavailable and must be updated. A 1.1.0 watch can still render the older passive cache from a 1.0.1 phone, but Smooch actions remain disabled until target-scoped configuration arrives. Data Layer transport success is not server delivery; the watch reports queued status until the phone accepts ownership, and requests simply expire after 15 minutes.
