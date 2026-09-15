# ADR 0029: Relationship invalidation purge protocol

- **Status:** Accepted for RC14
- **Date:** 2026-09-14

## Context

Relationship data is copied into several bounded stores so the phone, widget, notification worker, and watch can work offline. An unpair, sign-out, suspension, deletion, or stale request can race a network callback or delayed Wear Data Layer message. Clearing only the visible activity leaves drafts, media, alarms, notifications, or passive surfaces behind.

## Decision

The API returns the stable structured code `relationship_inactive` only after authenticating the account and determining that active membership or its couple no longer exists or has ended. Every active-couple lookup and lock uses this contract, including an unpair retry after a concurrent unpair. Android treats only that exact bounded code as a purge trigger; generic messages, malformed bodies, old-archive failures, and unrelated conflicts cannot erase local state.

One centralized phone purge advances the relationship generation before clearing authentication-scoped display caches, drafts, retained media, queued mutations and location samples, alarms, notifications, profile images, setup state, and widget state. It cancels relationship workers and publishes an urgent inactive record and durable purge marker to Wear. The unpair transaction also deletes the former couple's short-lived notification events and disables both members' random installation records. Asynchronous writers take the same relationship guard and recheck the generation before committing bytes.

Wear applies purge markers before data in each batch, rejects older generations and legacy replays, deletes pending and complete profile files, and refuses a new relationship payload until its generation and opaque relationship fingerprint are current. If disconnected, every Wear surface enforces a 24-hour authorization deadline locally. The phone widget applies the same active identity and deadline rule.

## Consequences

- Unpairing and invalidation remove relationship state even when messages arrive out of order.
- A temporarily disconnected watch becomes unavailable after 24 hours until the phone supplies current authorization.
- A false generic server error cannot trigger destructive local cleanup.
- Every new relationship-scoped cache or worker must join the centralized purge and generation protocol.
