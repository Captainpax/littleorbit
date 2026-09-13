# ADR 0022: Self-hosted per-device notifications

## Status

Accepted for RC12.1.

## Context

Smooch alerts previously used an account-wide polling acknowledgement. One phone could consume an event before another installation saw it, and the preference controlling lock-screen detail lived only on that phone. Little Orbit also needs optional document-edit alerts without adding Firebase, another hosted push provider, or document content to a notification broker.

## Decision

The FastAPI service stores account-level notification preferences, random app-installation IDs, short-lived partner events, and one delivery row per active installation. Smooch creation and the first accepted note edit create their event in the feature transaction. Note alerts use a 30-minute document/editor cooldown and are skipped while the recipient already has that document open.

Foreground Android clients keep an authenticated first-party WebSocket that carries only `notification.available`; the client then fetches authorized event metadata. WorkManager registers the installation, polls at Android's 15-minute minimum, posts enabled channels, and acknowledges only events Android accepted. Lock-screen public versions are always generic. Events expire after seven days, individual delivery attempts normally expire with their 24-hour event deadline, and installations unseen for 90 days are removed.

The deployment remains one API process because the in-memory foreground hint hub is process-local. Durable polling remains authoritative, so a missed hint delays delivery without losing it.

## Consequences

- No third party receives account or relationship notification data.
- Each enabled phone independently receives and acknowledges the same event.
- Foreground delivery is prompt when the socket is available; background timing remains subject to WorkManager and OEM limits.
- Preferences follow the account, while Android runtime permission and channel state remain installation-specific.
- Future multi-replica deployment needs a shared hint bus or must explicitly accept polling-only foreground behavior.
