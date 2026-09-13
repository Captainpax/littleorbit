# ADR 0020: Markdown Our Space and private attachments

- Status: accepted for RC11
- Date: 2026-09-12

## Context

Little Orbit's first note editor sent debounced body changes through a WebSocket observer while each save opened another socket. Server acknowledgements replaced the whole Android `EditText`, moving the cursor to the beginning and increasing the chance of duplicate or stale connection state. Notes were plain text and could not safely carry the images and documents couples use for ordinary planning.

Attachments add a second trust boundary. A filename, declared media type, or authenticated account cannot make uploaded bytes safe. Unbounded buffering can exhaust the home server, metadata can expose private device/location details, and a public file route can bypass the couple authorization model. Offline copies also outlive a network session unless the client gives them an explicit lifecycle.

## Decision

Android opens one authenticated editor WebSocket for snapshot, presence, operations, acknowledgements, and reconnect. It coalesces typing into code-point insert/delete operations with stable operation IDs. Acknowledgements carry the current server body and revision; Android applies the smallest UTF-16 range patch and maps the current selection through it. Disconnected edits remain app-private drafts. Unsafe divergence pauses mutation and shows local and server versions.

Our Space stores Markdown text. Android renders CommonMark with table, strikethrough, task-list, and autolink extensions. It does not enable raw HTML or a general network-image loader. Remote image syntax becomes a deliberate link, while attachment references use a private `attachment://` identifier and the authorized attachment tray.

Attachment metadata lives in PostgreSQL and bytes live in a private Compose volume. The API authorizes current couple membership before note or attachment lookup, locks the couple for quota reservation, accepts only fixed media types, limits each file to 100 MiB and a couple to 2 GiB, and accepts exact-offset chunks no larger than 4 MiB. An operation-ID replay must match the original filename, type, size, and digest.

Original bytes remain staged and unavailable. An isolated media worker streams them to ClamAV, then removes source metadata by rebuilding images/PDFs or remuxing audio/video. Clean sanitized bytes receive a new size and SHA-256 digest before availability. Scanner outages retry in a fail-closed state; malware, malformed content, digest mismatch, or sanitization failure deletes bytes and records a content-free rejection reason. Android verifies the sanitized digest before preview and may keep an explicit app-private offline copy. Deletion, relationship-state reset, and archived-note purge remove their corresponding private files.

## Consequences

The editor keeps cursor position stable for normal acknowledgements and uses one transport state machine per open document. Unicode offsets remain compatible with the server while Android selection mapping stays in UTF-16 units.

Attachments require a ClamAV definitions volume, shared private content volume, media worker, FFmpeg, Pillow, pypdf, backup pairing with PostgreSQL, and a restore drill. First startup is slower while signatures initialize. Files can remain pending during scanner outages and some malformed or metadata-removal-hostile files are rejected instead of being repaired silently.

The owner console may show aggregate pending/rejected counts. It has no attachment filename, byte, preview, or download surface. AI, Ollama, widgets, Wear tiles, and complications receive no note or attachment content.
