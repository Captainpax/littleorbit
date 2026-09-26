# ADR 0033: Age-encrypted coordinated backups

- **Status:** Accepted for RC14
- **Date:** 2026-09-14

## Context

PostgreSQL and the private attachment volume form one logical state set. A database-only backup leaves attachment references without bytes, while an attachment-only copy loses authorization and integrity metadata. Plaintext dumps and archives contain account and relationship data, and same-drive copies do not survive disk loss.

## Decision

A coordinated backup pauses API, worker, and media-worker mutations, streams a custom-format PostgreSQL dump and a manifest-bearing attachment tar directly through `age`, and restarts the exact containers that were running. No plaintext intermediate dump or archive is written. PostgreSQL uses a read-only backup role and excludes all `location_samples` table data. The attachment stream records relative paths, sizes, and SHA-256 values; restore validates every manifest entry before replacing bytes.

The age private identity stays outside Git and Docker with an offline recovery copy. Encrypted files have checksum sidecars and bounded retention. Restore occurs only into an isolated project or an approved maintenance window, pairs matching database and attachment snapshots, runs migrations, and verifies privacy-safe counts and synthetic content. Signed APKs and their immutable checksum metadata are backed up separately from mutable application state.

The 2026-09-14 drill restored an encrypted database and six attachment files into isolated state, proved raw location rows were absent, verified existing account/couple metadata without opening relationship content, and removed the disposable restore database and marker afterward.

## Consequences

- A stolen backup file is not usable without the separately protected age identity.
- Brief write unavailability provides a clear cross-store consistency point.
- A backup on the application drive protects against logical failure but not physical disk loss; an encrypted off-host copy remains required.
- Restore testing is part of backup completion, not an optional later step.
