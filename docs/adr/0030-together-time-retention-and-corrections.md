# ADR 0030: Together-time retention and corrections

- **Status:** Accepted for RC14
- **Date:** 2026-09-14

## Context

Together-time needs enough detail to recompute recent estimates and explain confidence without turning Little Orbit into location history. Couples also need a bounded way to correct a day when GPS evidence is missing or inaccurate. Keeping raw coordinates in backups would defeat their short retention window.

## Decision

Relationship age begins at the immutable confirmed pairing instant. With mutual consent, clients upload deduplicated, idempotent location batches containing time, coordinates, and accuracy. The server matches the two members in bounded time windows, incorporates both accuracy radii into the 100-metre decision, caps interpolation across missing samples, and stores at most one coordinate-free estimate per UTC minute.

Raw samples carry an explicit expiry no later than 24 hours after `recorded_at`; maintenance runs at least every five minutes. PostgreSQL backups exclude raw sample rows. Coordinate-free minute buckets remain for 30 days, after which maintenance retains only daily and lifetime totals. A member may replace one completed day's displayed total with a reason and expected revision. The update uses optimistic concurrency, records who and when for both partners, and sends only a content-free correction alert. Push and administrator surfaces receive neither coordinates nor the reason.

## Consequences

- Recent estimates can be recomputed while precise location has a short, enforceable lifetime.
- Older history supports totals but cannot reconstruct a route or minute-by-minute proximity.
- Corrections are transparent to both partners and conflicting edits require an explicit retry.
- Zero or low-confidence time remains a valid estimate when evidence is sparse.

## RC14 enforcement note — 2026-09-14

The ingestion deadline is scheduled five minutes before the absolute 24-hour limit so the five-minute maintenance cycle has time to delete the row. Samples that have already reached that safety margin are rejected rather than briefly reintroduced from an old offline batch. Maintenance also deletes any row whose `recorded_at` reached 24 hours, even when legacy or damaged expiry metadata claims a later deadline. A disposable PostgreSQL test covers both expiry paths.

Migration `0023` shortens every pre-existing later deadline to `recorded_at + 23 hours 55 minutes`. Its downgrade deliberately does not extend those deadlines again. A disposable `0022` to `0023` rehearsal verified a legacy 24-hour row becomes 23 hours 55 minutes before the same migration was applied to the hosted database.
