# AI agent guide

## Role

Own site-wide daily question generation, prompt/schema versions, validation, safety rules, evaluations, and deterministic curated fallback.

## Boundaries

The AI service may receive calendar dates, recent public question text/categories, prompt metadata, and model settings. It may never receive user or couple information in 1.0.

## Hard rules and invariants

- Use `qwen3:4b-instruct-2507-q4_K_M` through internal Ollama with one parallel request, 4096 context, bounded output, and `keep_alive: 0`.
- Require versioned structured JSON. Quarantine malformed or rejected output; never silently rewrite it into a publishable question.
- Reject identifying-data requests, coercion, manipulation, diagnosis, regulated advice, self-harm, minors, graphic sexual content, and unsafe location disclosure.
- Normalize and hash exact duplicates; use database trigram similarity for near duplicates in production.
- Maintain seven future local dates. Every date must have five publishable general questions even when Ollama is absent or times out.
- Persist model digest, prompt version, parameters, validation results, selections, quarantine reasons, and fallback reason.
- Inventory every repository-owned Markdown file for each AI update. Update or create all affected evaluation, privacy, operations, architecture, release, and contributor documents, and always review and update `ROADMAP.md` for behavior, scope, milestone, or release changes.

## Start here

- AI ADR: [`../../docs/adr/0003-private-local-ai.md`](../../docs/adr/0003-private-local-ai.md)
- Generation flow: [`../../docs/NETWORK-FLOW.md`](../../docs/NETWORK-FLOW.md)
- Public boundary: [`../../docs/PRIVACY.md`](../../docs/PRIVACY.md)

## Commands and required tests

```bash
python -m ruff check services/ai
python -m mypy services/ai
python -m pytest services/ai/tests
python -m little_orbit_ai.evaluate
```

Evaluate accepted and rejected fixtures, malformed JSON, unsafe text, exact/near duplicates, category repetition, timeouts, unavailable GPU, CPU fallback, OOM, quarantine, bank exhaustion, and seven-day coverage.

## Documentation impact

Prompt or schema changes require fixture/evaluation updates and a version bump. Model or privacy-boundary changes require an ADR and PRIVACY update.

## Common mistakes

- Including examples copied from real user content.
- Depending on the model to enforce safety or schema correctness.
- Retrying forever during an outage.
- Pulling an unpinned mutable model during application startup.
- Publishing fewer than five questions because generation failed.
