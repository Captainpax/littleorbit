# ADR 0041: Private quiz feedback and bounded weekly intelligence

Status: accepted

Date: 2026-09-20

## Context

Changing only the presentation of a question did not stop the generator from repeating the same idea. Little Orbit also had no direct, privacy-preserving way for a person to say whether a revealed global question was useful. Feeding answers, relationship history, or identifiable feedback into generation would violate the product boundary.

## Decision

Little Orbit 1.2 introduces `/v3/quizzes` and feedback for launch-forward global questions. A person may rate a question only after both partners have finished and the shared reveal exists. Feedback contains one to five stars, at most three fixed tags, and an optional 300-character review. Review submission requires a separate, initially unchecked consent. Each write has an operation ID and optimistic revision; only the author can read, edit, or delete linked feedback.

Linked feedback is editable for 30 days. Retention then removes account, couple, and quiz-day links while preserving only bounded question-quality values. Raw review text is deleted after 90 days. Weekly learning uses only global-question groups with at least five distinct accounts. The local model receives no answers, identifiers, notes, locations, custom questions, or relationship history.

Saturday learning produces a strict, bounded policy. Sunday generation creates the next Monday-through-Sunday pool. Both schedules use UTC and are configurable. A failed learning pass keeps the previous policy; failed generation leaves safe curated coverage in place. Policy activation and scheduled runs are idempotent and concurrency-safe.

Every generated question carries a stable concept family and short concept summary. Exact hashes, PostgreSQL trigram similarity, and pinned 768-dimensional Nomic embeddings compare candidates against 365 days of global questions. A formatting or interaction change therefore cannot disguise a repeated concept. Malformed, unsafe, or duplicate candidates are quarantined rather than silently repaired.

## Consequences

- Feedback is optional and never changes quiz completion or reveal.
- Administrators see only thresholded global intelligence and consented sanitized review text, never which account or couple supplied it.
- The AI boundary expands from public question metadata to thresholded, consented product feedback; it still excludes relationship content and answers.
- The service depends on PostgreSQL `vector` and a pinned local embedding model.
- Clients older than `/v3` keep their existing quiz behavior but cannot create feedback.
