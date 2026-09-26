# ADR 0001: Monorepo with a modular monolith API

- Status: Accepted
- Date: 2026-09-10

## Context

Little Orbit crosses Java, Python, TypeScript, Docker, and versioned contracts. It is run from one small home host and maintained as a learning project.

## Decision

Keep applications, services, protocol, infrastructure, and documentation in one repository. Implement the HTTP/WSS backend as a modular FastAPI monolith with a separate worker process using the same application packages. Keep feature boundaries explicit and transactions local to one PostgreSQL database.

## Consequences

Atomic pairing and note revisions remain straightforward, shared contracts can be tested across languages, and one Compose project operates the service. Modules must prevent a monolith from becoming unstructured; extraction into separate network services requires a later ADR and measured need.
