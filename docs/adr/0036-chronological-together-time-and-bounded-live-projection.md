# ADR 0036: Chronological together-time evidence and bounded live projection

- Status: accepted
- Date: 2026-09-16

## Context

The original proximity estimator greedily paired one sample from each phone. When the phones reported at different rates, an intervening observation could remain unmatched and disappear from the interval decision. The Android detail screen also fetched one aggregate once and displayed only hours and minutes, so it could not act like a live timer. Letting a phone add time indefinitely would be unsafe because one device cannot prove that both partners remain nearby.

## Decision

The server evaluates the chronological union of both retained sample streams. Every new observation is compared with the newest observation from the other member. Evidence is usable only when the two samples are at most five minutes apart. A nearby interval is counted only when both bounding decisions are nearby and no more than five minutes apart. Fractional boundaries are truncated instead of receiving a minimum one-second credit.

The durable value is coordinate-free observed nearby time. The v3 summary may also authorize a display-only projection after two consecutive nearby decisions. That projection is anchored to the server total and server time, expires five minutes after the older member's newest evidence, and is never persisted by Android. The visible phone screen advances it with Android's monotonic elapsed-realtime clock, polls the server every 30 seconds, and stops at the server deadline. A new authoritative response may reduce the projected display when later evidence does not confirm it.

Location batches carry the exact relationship ID and Android relationship generation. The Room 4-to-5 migration deletes legacy unscoped coordinate-queue rows rather than guessing which relationship owns them. New samples are encrypted locally, deduplicated by stable sample ID, and retained on temporary network or throttle failures. Revoked permission, consent, session, or relationship state stops collection and purges private state.

The visible foreground service requests a fix about every two minutes. WorkManager remains an inexact 15-minute recovery path. Both paths use the same queue and accounting engine. The older v1/v2 together-time writers return `410 Gone`; current clients use only v3.

Widgets and Wear surfaces show the latest server-observed nearby duration with a stale state. They do not extrapolate because passive surfaces cannot reliably receive the evidence needed to retract a projection.

## Consequences

Asymmetric phone cadence can no longer hide an intervening apart or poor-accuracy observation. One phone alone never renews freshness or a live deadline. The foreground detail screen feels live for a short, explicit evidence window without turning client animation into durable credit. Temporary API failures may delay upload but do not silently erase queued samples.

Existing daily totals are labeled `legacy` or `mixed` where appropriate; new coordinate-free estimates use algorithm version 3. Raw coordinates still expire within 24 hours and remain excluded from backups. The release requires a Room migration, an Alembic migration for estimate provenance, and a minimum supported phone version that understands the v3 state contract.
