# Little Orbit protocol

`schemas/v1` preserves the original HTTP, WebSocket, pairing, location, AI, RC10 Smooch, RC11 note-attachment, RC12 activity-page, and RC12.1 partner-notification payloads. The Smooch contract carries a fixed emoji, a versioned phrase key, UTC delivery time, sender-safe hourly allowance, and weekly totals without exposing relationship content to public routes. The attachment contract exposes authorized metadata, exact upload progress, scanner state, and the digest of the bytes currently safe to download; binary content stays outside JSON. The activity contract permits only fixed event metadata and rejects copied feature content. The notification contract carries a bounded event kind and authorized display metadata while forbidding note bodies and attachment data. `schemas/v2` defines RC5 generated-question batches and privacy-aware quiz days with typed answer shapes. `schemas/v3` makes the immutable pairing instant and derived pair age explicit alongside coordinate-free nearby-time estimates. Matching valid and invalid fixtures are consumed by Python, Java, and TypeScript tests.

RC8 adds the authenticated, content-limited orbit profile contract and the public immutable release-history contract used by the patch-notes page and RSS feed. Binary profile images remain outside JSON schemas and are always authorized separately.

RC10 keeps the older relationship-date endpoints for protocol compatibility, but clients render `paired_at` and `paired_days` from the v3 summary. A future removal of the unused proposal fields requires its own versioned contract and migration decision.

Rules:

- Schemas use JSON Schema draft 2020-12 and reject unknown fields.
- Instants are RFC 3339 strings with an explicit offset and are normalized to UTC by the server; local dates use `YYYY-MM-DD`; time zones use IANA names.
- IDs are opaque UUID strings. Clients must not infer ownership or ordering from them.
- Text operation offsets count Unicode code points, not UTF-16 code units or encoded bytes.
- Attachment operation IDs are scoped to a note and may resume only matching name, type, size, and original SHA-256 metadata. Download metadata changes to the sanitized size and digest only after a clean scan and successful metadata-removal pass.
- Notification delivery IDs are installation-scoped. Acknowledging one registered phone must not consume the event for another phone.
- Breaking changes require a new version directory. Compatible optional fields may be added within a version only after all supported clients tolerate them.
- A v2 quiz day has exactly five stable ordered questions. Partner answers remain `null` until the server has atomically marked the whole day revealed.
