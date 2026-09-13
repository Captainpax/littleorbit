# API agent guide

## Role

Own authenticated HTTP/WSS behavior, application transactions, persistence, scheduling entry points, and privacy enforcement.

## Boundaries

- Routes parse requests, invoke an application service, and map typed errors.
- Application services enforce authorization and own explicit transaction boundaries.
- Repositories perform persistence without policy decisions.
- Domain modules contain pure calculations and invariants.
- AI generation policy stays in `services/ai`; the API stores and serves validated results.

## Hard rules and invariants

- Check actor authorization before protected resource existence.
- Use Pydantic v2, SQLAlchemy 2 async APIs, Alembic, UTC instants, database constraints, and optimistic revisions.
- Hash passwords with Argon2id. Hash one-use tokens and recovery codes. Encrypt TOTP secrets at rest.
- Pair redemption uses a row lock and one transaction. A couple ends at two active members.
- Mutations exposed to retries require scoped idempotency keys.
- WSS connections authenticate before subscription and reauthorize after hub registration; note revisions are monotonic, operation IDs are unique per note, presence counts unique accounts, and archived notes reject edits.
- Attachment routes authorize before note/file lookup, lock couple quota, stream bounded exact-offset chunks, require matching idempotency replays, expose no unscanned bytes, and retain no server file after deletion or note purge.
- Attachment routes authorize before lookup, bind retry IDs to exact metadata, lock quota reservations, bound streams before buffering, and never serve bytes before clean scan plus metadata removal. Scanner outages fail closed.
- Lock the couple row for relationship-content mutations that must not race unpairing. Relationship age derives from the confirmed pairing instant.
- Enforce the Smooch rolling-hour limit in the same transaction that inserts the event. Private old-pairing history remains authorized to its original participant and is erased by either participant's account deletion.
- Record couple activity only while the caller holds the couple lock. Dedupe each event, advance a couple-local sequence monotonically, keep seen watermarks monotonic, purge after 30 days, and never copy note bodies, attachment names, quiz answers, coordinates, or other feature content into the feed.
- Audit security events with identifiers and outcomes, never credentials or relationship content.
- Trust forwarded client IP only when the direct peer equals the configured NPM address.
- Never mutate or unpublish a published APK record. A compatibility floor applies before authentication only after its explicit timezone-aware `required_after` instant.
- Serve APKs only from the versioned release directory after their file size and SHA-256 match published metadata. Preserve byte-range and HEAD behavior for interrupted mobile downloads.
- Inventory every repository-owned Markdown file for each API update. Update or create all affected protocol, privacy, operations, architecture, release, and contributor documents, and always review and update `ROADMAP.md` for behavior, scope, milestone, or release changes.

## Start here

- Protocol contracts: [`../../protocol/`](../../protocol/)
- Authentication ADR: [`../../docs/adr/0002-owned-authentication.md`](../../docs/adr/0002-owned-authentication.md)
- Pairing/network flows: [`../../docs/NETWORK-FLOW.md`](../../docs/NETWORK-FLOW.md)

## Commands and required tests

```bash
python -m ruff check services/api
python -m mypy services/api
python -m pytest services/api/tests
alembic -c services/api/alembic.ini upgrade head
```

Test expiry and replay, neutral public responses, throttles, honeypot, session rotation, authorization-before-existence, pair races, idempotency, note ordering/reconnect, Android version-floor timing, release immutability, artifact absence/corruption, byte-range downloads, deletion, precise-coordinate expiry, and admin redaction.

## Documentation impact

Update protocol fixtures for contracts, NETWORK-FLOW for request paths, PRIVACY for stored or exposed data, and an ADR for transaction or authorization changes.

## Common mistakes

- Calling `commit()` inside repositories.
- Returning ORM models from routes.
- Logging request bodies on authentication, notes, quizzes, or location routes.
- Using application checks where a database constraint is required for race safety.
- Treating WebSocket authentication as permanent after session revocation.
