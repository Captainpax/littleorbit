# Little Orbit protocol

`schemas/v1` is the language-neutral contract for HTTP and WebSocket payloads. `fixtures/v1` contains accepted and rejected examples consumed by Python, Java, and TypeScript tests.

Rules:

- Schemas use JSON Schema draft 2020-12 and reject unknown fields.
- Instants are RFC 3339 strings with an explicit offset and are normalized to UTC by the server; local dates use `YYYY-MM-DD`; time zones use IANA names.
- IDs are opaque UUID strings. Clients must not infer ownership or ordering from them.
- Text operation offsets count Unicode code points, not UTF-16 code units or encoded bytes.
- Breaking changes require a new version directory. Compatible optional fields may be added within v1 only after all clients tolerate them.
