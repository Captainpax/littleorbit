# ADR 0031: Opt-in sanitized crash diagnostics

- **Status:** Accepted for RC14
- **Date:** 2026-09-14

## Context

Crashes on particular Android and OEM versions are difficult to reproduce, but ordinary crash reporters can collect message text, device identity, breadcrumbs, or relationship content. Little Orbit needs useful failure grouping without creating another personal-data stream.

## Decision

Crash reporting is disabled by default and requires an explicit setting. Android builds a maximum 64 KiB report from the app version, validated exception class names, and Little Orbit class/method frame identifiers. It excludes exception messages, local variables, device identifiers, logs, request data, URLs, account state, and relationship content. A random installation identifier is hashed before storage.

The API validates the strict schema, accepts at most ten reports per installation per UTC day, and derives a SHA-256 fingerprint from the validated code identifiers. Structured exception and frame data expires after 30 days. The content-free fingerprint and version grouping expires after 90 days. Administrators may inspect aggregate versions and fingerprints, never a relationship timeline or user-entered text.

## Consequences

- Reports can identify repeated app-code failures while carrying no exception message or relationship payload.
- Some failures cannot be diagnosed without a person voluntarily providing separate reproduction details.
- Adding a diagnostic field requires a new privacy review, schema fixture, size analysis, and retention test.
