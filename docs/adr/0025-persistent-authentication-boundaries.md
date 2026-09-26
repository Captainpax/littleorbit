# ADR 0025: Persistent authentication and relationship-transition boundaries

- Status: Accepted
- Date: 2026-09-14

## Context

Process-local request counters reset on restart and cannot coordinate multiple API processes. An enabled administrator factor could be overwritten before the replacement was proven. A WebSocket authenticated only at connection time could retain access after session revocation. Password reset, session issuance, pairing, unpairing, and deletion also need one lock order so concurrent requests cannot preserve an old session or create conflicting relationships. Legacy quiz rows predate whole-day reveal state and need an explicit export rule.

## Decision

Store fixed-window request counters in PostgreSQL under scope-separated keyed subject hashes. Apply IP buckets first, cap counts at one over the configured limit, commit attempts independently of application work, remove expired scope rows during use, and purge inactive rows after 24 hours.

Use the account row as the outer lock for credential, session, and relationship-transition work. Lock multiple accounts in UUID order, then the couple, then memberships in account order. Relationship-content mutations acquire the couple lock before changing a membership. A successful password reset consumes every outstanding reset token and revokes every session in the same transaction. Every session issuer and rotator uses the account lock.

Keep an enabled administrator factor active while a separately encrypted replacement is pending. Starting replacement requires current password plus replay-safe current TOTP or one unused recovery code. Confirmation rechecks the exact calling session, pending expiry, and new TOTP; it then swaps factors, hashes new recovery codes, revokes every prior session, and issues one replacement session. Administrator configuration is assembled from an explicit safe allowlist.

Retain only an account identifier and keyed session digest in live note and notification connections. Revalidate after hub registration, before every client operation, and at least every 30 seconds while idle. A note mutation repeats the account, exact-session, membership, and note checks in its transaction. Treat loss of any required state as terminal.

Legacy quiz answers may enter an account export or former-relationship archive only when two distinct participants answered the same question in that relationship.

## Consequences

Migration `0017` is required before the RC14 API starts. Request attempts remain effective across restarts and API processes without retaining their raw subjects. Fixed windows are deliberately simple and may reject a legitimate burst until that subject's window expires; operators can tune bounded limits without changing code. Authentication and pairing writes may wait on one account lock, but their outcomes are deterministic and cannot race into a surviving stale session or a second active relationship. Revoked foreground sockets can remain connected for at most the 30-second idle-check interval, while operations are rejected at their next transaction boundary.
