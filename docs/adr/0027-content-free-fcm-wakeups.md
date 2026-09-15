# ADR 0027: Content-free FCM wake-ups

- **Status:** Superseded by ADR 0034
- **Date:** 2026-09-14

## Context

ADR 0022 made the Little Orbit API queue and per-installation delivery rows the source of truth for partner alerts. Foreground WebSocket hints are prompt, but Android may suspend both the app process and periodic WorkManager polling. That can delay a Smooch or a completed-quiz alert for many minutes. Sending relationship text through a hosted push broker would violate the privacy boundary.

## Decision

Little Orbit may use Firebase Cloud Messaging only as an optional wake-up transport. Its data payload is the fixed opaque signal `notification.available`; it contains no account, couple, event, note, quiz, Smooch, countdown, location, name, or installation identifier. The Android app authenticates to Little Orbit after the wake, fetches its own pending delivery rows, applies account preferences locally, and creates the private notification itself.

Each random installation owns a replaceable FCM token. Android stores its local copy as Android Keystore-protected ciphertext and removes the old plaintext preference during migration. The server encrypts the address and indexes it by a keyed digest. Reassignment takes a transaction-scoped lock derived from that digest, so concurrent installation heartbeats preserve one owner without exposing the token. A worker claim records the exact digest and attempt instant; its result changes the row only if both still match, so a delayed failure cannot erase a rotated address. When FCM explicitly rejects an address, the service deletes its ciphertext and retains only the non-reversible keyed digest so a polling heartbeat cannot restore the same dead value. Android deletes its ciphertext, retains only a rejection digest, and requests one Firebase delete-and-rotate operation; another rejection waits for an external rotation or configuration repair instead of creating a loop. Server acceptance clears that one-shot gate. The server never treats a successful FCM request as an event acknowledgement. Android acknowledges a delivery only after that installation accepts the local notification. High priority is used only when an unexpired, user-visible pending event exists. Devices without Google services, without configured Firebase values, or without notification permission retain the first-party WebSocket and WorkManager polling paths.

Ordinary Android wake requests coalesce without cancelling a running authenticated fetch. High-priority FCM signals use a separate, single expedited job, so repeated lifecycle or token callbacks cannot indefinitely restart notification delivery.

After the validated global question pool exists, the scheduled worker materializes the current UTC quiz for every valid active couple and creates one retry-safe `quiz_available` event per unfinished member. A phone status poll repeats the same operation as a fallback. AI improvement failure cannot block notification creation from an existing curated pool.

This decision changes only the optional wake-up transport in ADR 0022. The first-party queue remains authoritative and one installation cannot consume another installation's event.

## Consequences

- Google can observe that an app installation received an opaque wake-up, but receives no Little Orbit relationship content or account identifier.
- Background alert timing improves on supported Android devices while self-hosted polling remains functional.
- Production push requires four public Android identifiers plus a protected service-account credential and token-encryption key; partial configuration fails closed.
- Disabling push or deleting an installation removes the token without deleting another device's pending delivery.
