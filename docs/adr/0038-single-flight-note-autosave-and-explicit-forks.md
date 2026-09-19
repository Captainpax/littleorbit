# ADR 0038: Single-flight note autosave and explicit conflict forks

- Status: accepted
- Date: 2026-09-19

## Context

Manual and automatic Save actions could overlap while a newly created workspace was changing from its local identity to the returned server note ID. A lost response or lifecycle transition could then start another create. Offline edits also needed a safe response when the partner had already advanced the shared revision. Attachments made a simple body copy unsafe because every `attachment://` identifier belongs to one note.

## Decision

Android persists the new workspace and one stable creation operation ID synchronously before its first request. Create, title, and body mutations are serialized. Edits coalesce while one mutation is running. Autosave begins after 800 milliseconds without input and flushes at least every five seconds during continuous typing, on back navigation, and on lifecycle pause. Encrypted drafts survive network loss and process death.

Creation success adopts the returned note ID inside the same workspace before clearing the creation identity. A newer server revision stops synchronization and shows three explicit choices: review and merge, save the local work as a copy, or use the shared version. No conflict choice runs automatically.

Saving as a copy calls a retry-safe server fork. The server locks and reauthorizes the current couple, accepts references only to clean attachments owned by the source note, checks quota and disk admission, copies and verifies sanitized bytes, rewrites every attachment ID for the new note, and leaves the source unchanged. Any missing mapping fails closed.

Duplicate maintenance classifies exact active title/body groups without printing content. It automatically selects an attachment-owning or uniquely edited canonical note and may archive only untouched revision-zero, metadata-revision-zero duplicates with no attachments. Multiple attachment owners or multiple edited candidates are ambiguous and remain untouched. Applying archival requires a checksum-valid encrypted backup sidecar and retains the normal seven-day restore window.

## Consequences

Every implicit save retains one document identity. Offline work cannot silently overwrite a partner's newer revision, and a copied note cannot retain foreign attachment identifiers. The UI no longer needs an ordinary Save button, but it must communicate saving, recently saved, device-only offline, and review-required states. Recovery tooling is intentionally conservative and operationally gated.
