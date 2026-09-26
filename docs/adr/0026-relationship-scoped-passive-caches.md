# ADR 0026: Relationship-scoped passive caches

- **Status:** Accepted
- **Date:** 2026-09-14

## Context

The home widget, Wear launcher, tile, and complication must work when the phone is not immediately reachable. That also means cached relationship data can outlive the screen or process that authorized it. A stale label alone does not protect someone who signs out, unpairs, changes relationships, or loses phone-to-watch connectivity. Wearable Data Layer changes on different paths can also arrive in a different order, and an asynchronous thumbnail transfer can finish after a purge.

## Decision

The phone derives a 128-bit opaque relationship fingerprint from the immutable confirmed pairing instant. It never sends an account, couple, session, or email identifier to passive surfaces. A local generation uses wall-clock time as its ordering floor and increases for every activation or purge, including after a phone reinstall.

Display schema 3 and profile schema 2 carry the fingerprint, generation, active state, and authorization time. Sign-out, unpairing, account deletion, and `relationship_inactive` advance the generation, clear phone display state, and publish an urgent durable purge path plus inactive replacements. The phone still publishes the legacy display path for compatibility, but a watch that has observed a scoped generation rejects every later legacy record.

The watch applies all purge records before active records in a delivery batch. It clears display preferences, names, thumbnails, and partial thumbnail files before accepting a new relationship, rejects records older than its generation barrier, and rechecks the relationship generation before an asynchronous asset can replace a file.

Fresh passive data becomes visibly stale after six hours. Wear authorization expires 24 hours after the relationship-scoped authorization time carried by the phone record. The watch rejects an already-expired record instead of treating delayed delivery as new authorization, and rejects timestamps beyond a small clock-skew allowance. A best-effort alarm purges at the deadline, boot restores the check, and every launcher, tile, or complication read enforces the same rule. Expired surfaces show an unavailable prompt until the phone sends current data. The home widget also requires the current active phone relationship identity and stops rendering a cache after 24 hours.

## Consequences

- A disconnected watch can display useful estimates for a bounded period and then removes all relationship-scoped bytes without needing the phone.
- A valid relationship may appear unavailable after 24 disconnected hours until phone synchronization resumes.
- Purge safety does not depend on delivery order between the display, profile, and purge paths.
- A phone whose clock is moved behind an already observed generation after its app data is erased cannot replace that watch barrier until the clock is corrected or the valid generation advances.
- Passive caches remain deliberately small and contain no tokens, precise coordinates, note text, quiz answers, Smooch content, or attachment data.
