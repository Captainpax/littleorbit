# ADR 0035: Retry-safe note creation and mutual location freshness

- Status: accepted
- Date: 2026-09-15

## Context

An Android document workspace could lose its create identity during repeated UI actions and send new operation IDs containing the same just-saved content. Separately, the nearby-time process timestamp advanced from whichever phone uploaded most recently even when the partner stream had stopped. The first defect produced real duplicate rows; the second made an empty two-phone estimate appear current.

## Decision

Android owns one create coordinator per visible new-document workspace. It keeps a stable operation ID, allows one request in flight, and does not reset an already visible draft when the create action is repeated. The API still uses operation-ID idempotency and, while holding the current-couple lock, returns an exact active title/body match updated during the previous five minutes. This bounded fallback exists for clients that lose their local identity around a completed save.

Signed-in Android startup and sign-in re-arm the periodic sampler. Foreground paired screens reconcile permissions with each member's server consent, and the visible sampler uses Android's sticky restart contract. The server reports proximity freshness only through the earlier newest sample from both retained streams. All visible together-time surfaces lead with coordinate-free nearby duration; the confirmed pairing instant remains internal relationship metadata.

## Consequences

An intentional second document with identical title and body cannot be created during the five-minute recovery window; changing its title makes the intent unambiguous. Exact comparison occurs only after current-couple authorization and is never exposed through administration or logs. A phone collecting alone makes the estimate stale and adds no time. Raw-coordinate ingestion, 24-hour expiry, two-sample confidence, opt-out deletion, and backup exclusion remain unchanged.
