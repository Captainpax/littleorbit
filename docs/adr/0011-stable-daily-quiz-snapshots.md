# ADR 0011: Stable UTC daily quiz snapshots

- Status: Accepted
- Date: 2026-09-12

## Context

The first quiz endpoint treated each question as an independent submission and could reveal answers one at a time. It also let a changing global pool alter what a couple saw during the same day. Partner guessing lacked a separate self answer, weighted questions used one generic slider, and custom scheduling required a date chosen by the client.

## Decision

RC5 creates one immutable, ordered five-question snapshot per couple and UTC date under a database lock. Due custom questions fill FIFO slots first, up to all five. Remaining slots use that date's global pool; one consent-gated intimacy alternative may replace a general slot only while both partners opt in.

Each account saves private, typed, revisioned drafts with idempotent operation IDs. Finishing marks the whole set complete. A person may reopen before reveal. The transaction that observes both members complete sets one shared reveal timestamp, after which both full answer sets become readable. Incomplete days are editable for seven days and visible for 30.

Partner guessing stores a self choice and a guess for the other person. Weighted choice stores a one-to-five rating for every question-specific option with explicit low and high anchors. The UI celebrates partner-guess matches without scores.

Android polls a content-free status endpoint with WorkManager. Notifications can announce partner completion or reveal, but the response and device notification state contain no question or answer content.

## Consequences

- Both people always answer the same stable set even if generation, moderation, or consent changes later that day.
- Optimistic revisions and idempotency keys make retries safe, while stale edits return an explicit conflict.
- The reveal boundary is easy to audit because no partner answer is serialized before `revealed_at` exists.
- UTC creates one shared rollover worldwide and must be explained in the interface.
- Seven-day catch-up and 30-day history add retained quiz metadata and require bounded queries.
