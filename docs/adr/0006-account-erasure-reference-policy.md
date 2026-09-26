# ADR 0006: Account erasure and retained operational references

- Status: Accepted
- Date: 2026-09-11

## Context

Expired pair-code rows and note-operation history can still reference an account when its deletion job runs. Retaining those foreign keys would block erasure, while deleting shared operational history could damage the other person's private archive.

## Decision

Delete account-owned mail outbox entries and set account references in expired pairing and retained note-operation records to null. Keep the note revision and operation shape without its former actor identifier. Database foreign keys enforce `ON DELETE SET NULL`, and the account model exposes no reverse path from an anonymized reference.

## Consequences

Account deletion completes without deleting the other member's archived shared state. Historical operations can no longer identify the erased actor. Migration and deletion tests must cover these references whenever a new account foreign key is added.
