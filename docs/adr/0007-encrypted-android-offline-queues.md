# ADR 0007: Encrypted ordered Android offline queues

- Status: Accepted
- Date: 2026-09-11

## Context

Countdown edits and location samples must survive routine disconnection without leaking private data or creating duplicate server mutations after retries.

## Decision

Store pending Android mutations in Room as encrypted payloads using a Keystore-protected key. Preserve insertion order, include stable operation identifiers and optimistic base revisions, and replay through bounded WorkManager jobs. Keep note drafts local and require explicit reconciliation when their server base revision has changed. Clear account-scoped caches and queues at sign-out.

## Consequences

Retries remain idempotent and private payloads are not stored as Room plaintext. UI state must distinguish pending, failed, stale, and conflict states. Instrumented tests on supported Android versions remain a release gate because Keystore and scheduler behavior cannot be proven by host unit tests alone.
