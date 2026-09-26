# ADR 0044: Partner-assigned relationship names

Status: accepted

Date: 2026-09-20

## Context

Account display names are account identity, but couples often use a private name for one
another. Reusing an email-shaped account fallback in notifications also exposed more contact
information than the notification needed. A shared nickname must not let someone rename
themselves, escape the current relationship, or survive an unpairing.

## Decision

Each active partner may assign or reset only the other current member's relationship name.
Both members see the same resolved name in Little Orbit, notifications, activity metadata,
and managed Wear records. Account display names remain unchanged. A privacy-safe `You` or
`Your partner` fallback replaces account values that look like an email address, phone number,
or URL.

Names are NFKC-normalized, contain 1–40 Unicode code points, may include emoji and a zero-width
joiner, and reject controls, line breaks, email addresses, phone numbers, and URLs. Mutations
use a stable operation ID plus the expected name revision. Android encrypts one pending
operation before network use and replays it after an offline or process-death interruption.

The API authorizes the active relationship before reading or mutating its name record. The
resulting activity item is content-free and creates no partner notification. Names are included
in the account export, remain unavailable to Big Orbit and AI, and are deleted immediately with
the relationship during unpairing. Completed operation records expire after 30 days.

## Consequences

- One person controls the name applied to their partner, never their own relationship name.
- A stale revision returns a conflict and Android refreshes instead of overwriting the newer
  value.
- The relationship generation and purge boundary already used by Android and Wear prevent an
  old cached name from returning after sign-out, unpairing, or relationship replacement.
- Migration `0029` adds only relationship-scoped names and idempotency metadata; public account
  identity, pairing contracts, and the Wear protocol version do not change.
