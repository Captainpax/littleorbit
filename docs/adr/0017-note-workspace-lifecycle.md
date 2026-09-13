# ADR 0017: Multi-note workspace lifecycle

Status: Accepted for RC10

## Context

One shared document could not represent lists, plans, and ongoing thoughts cleanly. Multiple observer sockets also made one account appear as two present partners.

## Decision

Each couple may own multiple titled plain-text notes. Body operations retain server-authoritative transformation, monotonic revisions, stable operation IDs, acknowledgements, and explicit conflict snapshots. Android debounces body edits for 750 milliseconds and binds asynchronous results to the initiating note ID. Metadata operations rename or archive a note idempotently. Archived notes reject body edits, remain restorable for seven days, then are purged. Presence counts unique authenticated account IDs rather than sockets.

Every content or metadata mutation locks and reauthorizes the current couple so unpairing cannot race an accepted edit.

## Consequences

The UI gains a list/detail workspace and explicit recovery. Metadata has its own revision path. Presence remains approximate across disconnects but cannot claim both partners merely because one account opened multiple connections.
