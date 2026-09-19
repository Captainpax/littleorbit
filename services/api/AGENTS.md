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
- Commit public authentication, recovery, pair-redemption, and administrator-proof throttles independently in PostgreSQL. Persist only domain-separated subject hashes, apply IP limits first, cap counters, and purge expired rows.
- Lock an account before issuing, rotating, or revoking its sessions. A successful password reset locks the account and every outstanding reset token, consumes the complete token set, changes the password, and revokes all sessions in one transaction.
- Enabled administrator MFA replacement requires current password plus current TOTP or one unused recovery code. Keep the old factor active while a bounded encrypted challenge is pending; confirmation swaps factors and revokes every prior session.
- Pair creation, redemption, confirmation, unpairing, and deletion recheck eligibility after locking. Use the global transition order: account rows in UUID order, couple row, then membership rows in account order. Relationship-content mutations lock the couple before any membership row.
- Pair redemption uses a row lock and one transaction. A couple ends at two active members.
- Mutations exposed to retries require scoped idempotency keys.
- Note creation first honors the exact operation ID. Bounded exact-content recovery for a recently saved current-couple note runs only after authorization and the couple lock; it must not expose content, cross couples, or replace ordinary note IDs.
- WSS connections authenticate before subscription and reauthorize after hub registration, on every operation, and at least every 30 seconds while idle. A revoked, expired, suspended, deleted, unpaired, or disabled-device state closes the socket; note revisions are monotonic, operation IDs are unique per note, presence counts unique accounts, and archived notes reject edits.
- Attachment routes authorize before note/file lookup, lock couple quota, stream bounded exact-offset chunks, require matching idempotency replays, expose no unscanned bytes, and retain no server file after deletion or note purge.
- Attachment routes authorize before lookup, bind retry IDs to exact metadata, lock quota reservations, bound streams before buffering, and never serve bytes before clean scan plus metadata removal. Scanner outages fail closed.
- Lock the couple row for relationship-content mutations that must not race unpairing. Relationship age derives from the confirmed pairing instant.
- Nearby-time processing evaluates every chronological observation and never greedily discards a faster stream. Direct intervals, member skew, mutual freshness, and live projection remain bounded to five minutes. A later strong nearby anchor may confirm an otherwise unknown gap up to 20 minutes only when no intervening observation says apart or poor accuracy; persist that bridge provenance separately. Freshness uses the older newest retained sample from both members, so one uploading member cannot make the result current. Lock the couple before inserting or reconciling a batch, and preserve corrections while replacing only uncorrected estimates.
- Return the exact structured `relationship_inactive` 409 after authentication whenever active membership or its couple disappears or ends; Android uses only that bounded code to purge local relationship state. Keep archive and ordinary conflict errors distinct.
- Enforce the Smooch rolling-hour limit in the same transaction that inserts the event. Private old-pairing history remains authorized to its original participant and is erased by either participant's account deletion.
- Create partner alerts in the accepted feature transaction, deliver independently per active installation, and acknowledge only the authenticated account's installation. Legacy account-wide state never suppresses a current delivery. Backfill is conflict-safe; preference disablement and unpairing discard waiting alerts. Expose only authenticated first-party WSS hints and HTTPS polling; never store a hosted-provider address or call a hosted push broker. Note-edit alerts use a 30-minute document/editor cooldown and are skipped while the partner already views the note.
- Isolate lazy quiz-availability creation in a nested transaction. A missing question pool may suppress only that quiz event and must not roll back, hide, or delay unrelated pending notifications.
- Authorize and lock the active couple before relationship-avatar lookup or mutation. The caller may mutate only the partner's avatar; enforce subject and assigner inequality in the database and delete both avatars on unpair.
- Validate countdown timing kind, timezone, and timed/all-day field combinations before storage. Reminder offsets belong to the caller and must never appear in the partner's response or event metadata.
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
