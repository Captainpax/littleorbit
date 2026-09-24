# ADR 0045: Themed, retrieval-grounded weekly quizzes

Status: accepted

Date: 2026-09-23

## Context

The 1.2 weekly learner could improve broad writing policy, but its UTC schedule, small curated fallback, and prompt-only guidance did not provide a deliberate weekly arc. Exact and semantic duplicate checks prevented many repeats, yet an outage could still overuse a small bank. Public observances can make quizzes timely, but arbitrary browsing or personalized retrieval would weaken the privacy boundary.

## Decision

Little Orbit 1.3 runs the quiz cycle in `America/Los_Angeles` by default. Saturday at 09:00 processes only newly eligible K-anonymous feedback, evaluates a bounded learned policy, refreshes allowlisted public context, and plans one Monday-through-Sunday arc. Each day has a distinct theme. No more than two days in a week may center an inclusive observance. Sunday at 09:00 generates and publishes the seven validated daily pools.

Every general day contains exactly three theme questions and two variety questions, ordered across one light, two reflective, and two deeper prompts. These are editorial depth labels, not psychological assessments. Intimacy alternatives remain consent-centered and separately gated.

Reviewed Markdown is an allowlisted knowledge source. The service validates a manifest, chunks the files to at most 512 characters, stores their hashes and embeddings in PostgreSQL/pgvector, and retrieves only bounded excerpts for theme planning or question writing. Feedback changes policy; it does not fine-tune model weights. Public context still comes only from exact code-owned HTTPS sources and remains untrusted quoted inspiration. A source may use its most recent sanitized snapshot for 30 days; otherwise generation falls back to reviewed knowledge and reserve content and raises a content-free owner alert.

The offline reserve contains 1,825 general and 365 intimacy questions derived from reviewed templates. Every entry has immutable identity, content hash, concept metadata, review tier, and one-use consumption state. A representative 20 percent of general entries and every intimacy template receive the stricter review tier. The reserve is not permission to bypass schema, safety, composition, or 365-day semantic duplicate gates.

Generated global content is rejected when it repeats a same-day, same-week, or preceding-365-day concept by normalized hash, concept family, trigram similarity, or pinned local embeddings. Couple-authored custom questions are intentionally outside this global editorial rule. Model failure never removes already seeded coverage, and only a fully validated week moves to published state.

## Consequences

- Quiz headings can show the public weekly and daily themes without exposing feedback or generation internals.
- Saturday and Sunday scheduling follows a named IANA timezone, including daylight-saving transitions.
- Big Orbit may show content-free schedule, knowledge, context, reserve, theme, and run health and may request a typed future-week regeneration.
- Repository-owned knowledge becomes production input and therefore requires ordinary code review, hashing, documentation inventory, and release review.
- The model remains replaceable and local; no user or relationship data is added to retrieval, browsing, embeddings, or prompts.

