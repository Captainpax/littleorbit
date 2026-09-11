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

## System invariants

- A couple has exactly two active, verified accounts.
- Pair codes are eight characters, single-use, expire after ten minutes, and are redeemed atomically only after creator confirmation.
- Verification and reset tokens are stored as hashes, expire, and are consumed once.
- Quiz responses remain hidden until both partners submit.
- Intimacy questions require both partners' current opt-in; either opt-out takes effect immediately.
- Note operation IDs are idempotent and server revisions increase monotonically.
- Together-time sessions never overlap; uploaded samples are deduplicated and results are labelled estimates.
- Only the gateway binds a public host port. Ollama remains internal and accepts calls only from the AI service.

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
```

## Cross-system verification

Contract changes require valid and invalid fixtures, Python tests, web validation, Android parsing tests, and a version note. Authentication, pairing, notes, AI, location, or deployment changes also require the corresponding Mermaid flow and privacy/operations document to be checked.

## Documentation impact

Update the README for public behavior, SHOWCASE for visible changes, ROADMAP for scope, NETWORK-FLOW for trust or transport changes, PRIVACY for data changes, and an ADR for a durable architectural decision.

## Common mistakes

- Treating an authenticated user as authorized for their partner's data.
- Retrying a mutation without an idempotency key.
- Trusting forwarded headers from a peer other than Nginx Proxy Manager.
- Displaying stale widget or watch data without a stale indicator.
- Silently repairing malformed AI output instead of quarantining it.
- Claiming tests passed when a tool, emulator, device, GPU, or network path was unavailable.
