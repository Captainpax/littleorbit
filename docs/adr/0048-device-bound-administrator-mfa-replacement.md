# ADR 0048: Device-bound administrator MFA replacement

Status: accepted

Date: 2026-09-27

## Context

ADR 0025 introduced staged administrator-factor replacement while an enabled
factor remained active, but its replacement detail assumed a generic calling
administrator session. Privileged administration has since moved entirely to
Big Orbit, whose ordinary sessions are bound to an approved P-256 device. A
copied ordinary account token must not be enough to start or confirm a factor
change, and a successful rotation must not replace a device-bound session with
an unbound bearer. First-factor enrollment already has a separate restricted
terminal-PIN bootstrap under ADR 0046.

## Decision

Expose enabled-factor replacement only through Big Orbit's `/v2/admin/mfa`
routes. Both start and confirm require an exact Big Orbit principal and recheck
the account, approved device, and calling device session under the account,
device, then session lock order. An ordinary account session is rejected.

Starting replacement requires the current password and exactly one replay-safe
current TOTP or unused recovery code. An administrator without an enabled
factor cannot use this route; initial enrollment remains exclusive to the
restricted terminal-PIN bootstrap. The old factor stays active while the new
encrypted secret is pending. The challenge returns one authenticator URI plus
server-rendered PNG and SVG data URLs so Big Orbit can display the same secret
without delegating it to a browser or third-party renderer.

Confirmation requires the same exact device-bound session and the new TOTP.
The server swaps the factor, stores only hashes of the new recovery codes,
revokes every earlier administrator session, and issues one replacement
session bound to the same approved device. Recovery codes are returned once.

This decision supersedes only the administrator-MFA replacement detail in ADR
0025. Its persistent throttles, account-first lock boundaries, relationship
transitions, WebSocket revalidation, and legacy reveal rules remain accepted
unchanged. ADR 0046 continues to govern first-factor bootstrap.

## Consequences

- Password and current-factor proof alone cannot rotate MFA without possession
  of an approved Big Orbit device session.
- A successful factor change invalidates every prior administrator session but
  preserves the initiating device boundary through its newly issued session.
- A first owner must use the short-lived terminal-PIN/key-proof bootstrap;
  replacement no longer doubles as an initial-enrollment path.
- Big Orbit must protect the QR, pending secret, recovery codes, and local
  replacement-token write against screenshots, saved state, logs, and stale
  local-session races. If local storage fails after server confirmation, the
  operator must recover by signing in with the new factor or rotating again;
  the server does not re-display recovery codes.
- The change affects the Big Orbit operational contract only and does not add
  fields to Little Orbit's versioned cross-language mobile protocol fixtures.
