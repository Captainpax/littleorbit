# ADR 0017: Multi-note workspace lifecycle

Status: Accepted for RC10

## Context

One shared document could not represent lists, plans, and ongoing thoughts cleanly. Multiple observer sockets also made one account appear as two present partners.

## Decision

Each couple may own multiple titled plain-text notes. Body operations retain server-authoritative transformation, monotonic revisions, stable operation IDs, acknowledgements, and explicit conflict snapshots. Android debounces body edits for 750 milliseconds and binds asynchronous results to the initiating note ID. Metadata operations rename or archive a note idempotently. Archived notes reject body edits, remain restorable for seven days, then are purged. Presence counts unique authenticated account IDs rather than sockets.

Every content or metadata mutation locks and reauthorizes the current couple so unpairing cannot race an accepted edit.

Android closes the note editor WebSocket whenever the activity loses foreground focus. It keeps the encrypted body, title, base revision, and both selection endpoints, then fetches a fresh authorized HTTP snapshot before opening a new editor session. A delayed load cannot reopen a background presence socket.
Each connection also receives a local generation number. Callbacks must match both the selected note and the current generation, so a late acknowledgement or presence update from a closed socket cannot mutate a newly reconnected editor for the same note.

While the foreground library is visible, Android fetches its authorized directory at a bounded five-second interval. Identical ordered ID, revision, metadata, title, and body snapshots do not rebuild the view. A manual Refresh action remains available, background activities stop polling, and only the exact structured `relationship_inactive` response disables refresh and starts local pair-data cleanup.

## Consequences

The UI gains a list/detail workspace and explicit recovery. Metadata has its own revision path. Presence remains approximate across disconnects but cannot claim both partners merely because one account opened multiple connections or left the app in the background.
