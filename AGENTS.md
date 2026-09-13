# Little Orbit agent guide

## Role

Build a free, private couples platform that is understandable enough to learn from and safe enough to self-host. Work with owl discipline: inspect quietly, trace completely, then change deliberately.

## Boundaries

- `apps/android/`: Java/XML Android, widgets, and Wear OS.
- `apps/web/`: public Next.js site and owner console.
- `services/api/`: HTTP/WSS application and worker entry points.
- `services/ai/`: private Ollama adapter, validation, prompts, and evaluations.
- `protocol/`: versioned cross-language contracts and fixtures.
- `infra/`: containers, gateway, backup, and deployment configuration.
- `docs/`: public architecture, privacy, operations, and decisions.

Read the closest nested `AGENTS.md` before editing within one of these systems.

## Hard rules

1. Keep every feature free. Never introduce ads, tracking sales, premium gates, or paid unlocks.
2. Authorization precedes resource lookup. Public responses must not reveal whether protected data exists.
3. Administrators may inspect operational metadata, never relationship content, answers, notes, precise locations, or exports.
4. AI receives no user, couple, answer, note, email, location, or relationship data in 1.0.
5. Raw coordinates expire within 24 hours. Unpairing stops sharing immediately.
6. Store secrets outside Git. Logs and audit events must omit tokens, passwords, TOTP secrets, recovery codes, and personal content.
7. Use Java 17/XML in Android production code, Python with strict typing in services, and strict TypeScript in the web app.
8. Keep modules below 500 logical lines, functions/methods below 60 lines, and cyclomatic complexity at most 10. A ratcheted baseline may document existing exceptions and may only decrease.
9. Preserve unrelated work. Never guess a secret, DNS state, proxy state, or production state.
10. For every update, inventory all repository-owned Markdown files and check whether each remains accurate. Update or create every affected document, and always review and update `ROADMAP.md` when behavior, scope, milestones, or release state changes.

## System invariants

- A couple has exactly two active, verified accounts.
- Pair codes are eight characters, single-use, expire after ten minutes, and are redeemed atomically only after creator confirmation.
- Verification and reset tokens are stored as hashes, expire, and are consumed once.
- Quiz responses remain hidden until both partners submit.
- Intimacy questions require both partners' current opt-in; either opt-out takes effect immediately.
- Note operation IDs are idempotent and server revisions increase monotonically.
- Note attachments authorize the current couple before lookup, reserve bounded quota, remain unavailable until a clean scan and metadata-removal pass, and are verified by their sanitized digest before preview.
- Note attachment uploads use exact offsets and stable operation IDs; unscanned bytes are never served, private files remain couple-authorized, and deletion or note purge removes stored bytes.
- Note presence counts unique authenticated accounts; archived notes reject content operations and are recoverable for seven days.
- Couple activity is a 30-day, content-free metadata timeline. It may name a note or countdown but never stores note bodies, attachment names, quiz answers, locations, or custom Smooch text.
- Relationship age begins at the immutable confirmed pairing instant. Together-time sessions never overlap; uploaded samples are deduplicated and results are labelled estimates.
- A Smooch uses one approved emoji and phrase key, is limited to five sends per account in a rolling hour, survives unpairing in private archives, and is erased when either original participant deletes their account.
- Partner notification preferences belong to the account; delivery acknowledgements belong to one random installation ID. Foreground WSS hints contain no event content, lock-screen public versions stay generic, and acknowledging one phone never consumes another phone's delivery.
- Only the gateway binds a public host port. Ollama remains internal and accepts calls only from the AI service.
- Published APK metadata and first-party APK bytes are immutable. Android accepts an update only when its trusted URL, package, increasing version code, exact byte count, APK hash, and pinned signing certificate all match.
- Android release metadata comes from the signed build's generated manifest, which reads phone and Wear module metadata independently. Never infer one module's version code from the other.
- Background update checks fetch metadata only. APK download and installation always follow an explicit person action.

## Owl discipline

1. Inspect current state and the nearest guide before editing.
2. Trace a request across every trust boundary before changing it.
3. State invariants before implementing authorization, concurrency, location, or AI behavior.
4. Test failure, retry, duplicate, stale, offline, race, and unauthorized paths.
5. Update focused tests, public docs, internal diagrams, and agent guidance with code.
6. Report what was actually verified; never imply hardware or production testing that did not occur.

## Start here

- Product and setup: [`README.md`](README.md)
- Architecture and routing: [`docs/NETWORK-FLOW.md`](docs/NETWORK-FLOW.md)
- Privacy boundaries: [`docs/PRIVACY.md`](docs/PRIVACY.md)
- Decisions: [`docs/adr/`](docs/adr/)
- Contribution workflow: [`CONTRIBUTING.md`](CONTRIBUTING.md)

## Command map

```bash
docker compose --env-file .env -f infra/compose.yaml -f infra/compose.dev.yaml config
docker compose --env-file .env -f infra/compose.yaml -f infra/compose.dev.yaml up --build
python -m pytest services/api/tests services/ai/tests
python -m ruff check services
python -m mypy services
npm --prefix apps/web run check
npm --prefix apps/web run test
./gradlew :apps:android:mobile:testDebugUnitTest :apps:android:mobile:lintDebug
./infra/scripts/smoke-stack.ps1 up
./infra/scripts/android-smoke.ps1 -Serial <emulator-serial> -AccountIndex 0 -ResetApp
```

## Cross-system verification

Contract changes require valid and invalid fixtures, Python tests, web validation, Android parsing tests, and a version note. Authentication, pairing, notes, AI, location, updates, or deployment changes also require the corresponding Mermaid flow and privacy/operations document to be checked.

## Documentation impact

Update the README for public behavior, SHOWCASE for visible changes, ROADMAP for scope, NETWORK-FLOW for trust or transport changes, PRIVACY for data changes, and an ADR for a durable architectural decision.

## Common mistakes

- Treating an authenticated user as authorized for their partner's data.
- Retrying a mutation without an idempotency key.
- Trusting forwarded headers from a peer other than Nginx Proxy Manager.
- Displaying stale widget or watch data without a stale indicator.
- Silently repairing malformed AI output instead of quarantining it.
- Claiming tests passed when a tool, emulator, device, GPU, or network path was unavailable.
