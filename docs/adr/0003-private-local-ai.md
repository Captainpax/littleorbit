# ADR 0003: Private local AI for global daily questions

- Status: Accepted
- Date: 2026-09-10

## Context

Daily question variety benefits from generation, while user privacy, cost, home hardware, and offline resilience rule out a mandatory hosted AI dependency.

## Decision

Run pinned Ollama with `qwen3:4b-instruct-2507-q4_K_M` inside the private Compose network. Generate site-wide calendar pools with no user data. Validate strict JSON through deterministic safety, schema, duplicate, and category gates. Quarantine failures and fill shortages from a curated bank.

## Consequences

The approximately 2.5 GB Q4 model fits a 6 GB RTX 4050 Laptop GPU with headroom and can fall back to CPU. Generation quality must be evaluated, the image/model digest pinned for releases, and seven-day curated coverage maintained through outages.
