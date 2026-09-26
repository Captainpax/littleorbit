# ADR 0005: Server-authoritative plain-text note operations

- Status: Accepted
- Date: 2026-09-10

## Context

Two partners need live shared plain-text notes, offline drafts, retry safety, revision history, and understandable conflict behavior without adopting a complex opaque editor stack.

## Decision

Use authenticated WebSockets with server-monotonic revisions, stable client operation IDs, acknowledgements, and operational transformation for concurrent insert/delete operations. Persist operation history. When a disconnected draft cannot be transformed safely against retained history, return both versions for explicit user reconciliation.

## Consequences

The algorithm needs Unicode-aware offsets and convergence fixtures across Python, Java, and TypeScript. The server remains authoritative; clients never discard a draft silently.
