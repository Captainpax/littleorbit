# ADR 0043: Allowlisted public context and testable encrypted operations

Status: accepted

Date: 2026-09-20

## Context

Better global questions benefit from limited cultural and relationship-education context, but general web access would create prompt-injection, tracking, and server-side request-forgery risk. Backups also need recurring evidence that encrypted bytes can actually be restored without exposing relationship content.

## Decision

A dedicated fetcher may retrieve only exact HTTPS URLs present in both code and the database allowlist. It rejects redirects, non-public DNS results, unexpected content types, and responses larger than 64 KiB. It has no application secrets or private-network connection. The worker receives bounded text through a private one-way service link, strips active HTML and instruction-shaped text, and treats the result as untrusted inspiration. The model still receives no account or relationship data.

The host creates a coordinated age-encrypted database and attachment snapshot daily at 06:00 local host time. Feedback rows that remain attributable, idempotency records, anonymous raw reviews, precise coordinates, and collection-health snapshots are excluded from database dump data. An atomic manifest binds the exact two encrypted files by path, size, and SHA-256. An optional absolute filesystem destination outside the repository receives that pair, both checksum sidecars, and the pair manifest through a hash-verified partial-directory promotion.

At 07:00 each Tuesday, a restore drill resolves the newest completed pair manifest and verifies both encrypted artifacts before streaming the database into a uniquely named disposable database. It validates expected 1.2 tables, confirms excluded tables contain no restored rows, streams every attachment through its manifest and SHA-256 verifier without replacing the live volume, and drops only the validated disposable database name. Big Orbit may request `backup` or `test_restore`; a host runner atomically claims those fixed jobs and records content-free outcome metadata.

## Consequences

- The context fetcher can reach the public internet but cannot select an arbitrary URL or address.
- Changing the allowlist requires code review and a database migration or explicit operator action.
- Scheduled-task registration is an explicit host operation; checking in the script does not mutate a machine.
- A successful drill proves current encrypted artifacts are structurally restorable, not that a full disaster recovery or production failover has occurred.
- The age private identity remains outside Git, Docker, and off-host backup storage.
