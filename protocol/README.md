# Little Orbit protocol

`schemas/v1` preserves the original HTTP, WebSocket, pairing, location, AI, and RC10 Smooch payloads. The Smooch contract carries a fixed emoji, a versioned phrase key, UTC delivery time, sender-safe hourly allowance, and weekly totals without exposing relationship content to public routes. `schemas/v2` defines RC5 generated-question batches and privacy-aware quiz days with typed answer shapes. `schemas/v3` makes the immutable pairing instant and derived pair age explicit alongside coordinate-free nearby-time estimates. Matching valid and invalid fixtures are consumed by Python, Java, and TypeScript tests.

RC8 adds the authenticated, content-limited orbit profile contract and the public immutable release-history contract used by the patch-notes page and RSS feed. Binary profile images remain outside JSON schemas and are always authorized separately.

RC10 keeps the older relationship-date endpoints for protocol compatibility, but clients render `paired_at` and `paired_days` from the v3 summary. A future removal of the unused proposal fields requires its own versioned contract and migration decision.

Rules:

- Schemas use JSON Schema draft 2020-12 and reject unknown fields.
- Instants are RFC 3339 strings with an explicit offset and are normalized to UTC by the server; local dates use `YYYY-MM-DD`; time zones use IANA names.
- IDs are opaque UUID strings. Clients must not infer ownership or ordering from them.
- Text operation offsets count Unicode code points, not UTF-16 code units or encoded bytes.
- Breaking changes require a new version directory. Compatible optional fields may be added within a version only after all supported clients tolerate them.
- A v2 quiz day has exactly five stable ordered questions. Partner answers remain `null` until the server has atomically marked the whole day revealed.
