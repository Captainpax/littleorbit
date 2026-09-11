# ADR 0008: Separate app and owner-console session lifetimes

- Status: Accepted
- Date: 2026-09-11

## Context

The Android client and its background workers need to remain usable between ordinary app launches. A 30-minute opaque session expires before many background jobs run, and 1.0 does not issue a separate long-lived refresh credential. The owner console has broader operational authority and should retain a short session after password and TOTP authentication.

## Decision

Issue regular app sessions for 30 days and owner-console sessions for 30 minutes. Keep both values bounded and independently configurable. Store only opaque-token hashes on the server and encrypted app tokens on Android. Continue to revoke sessions on sign-out, password reset, account deletion, suspension, and explicit owner action. Keep atomic session rotation available for later client renewal work.

## Consequences

Android remains signed in between launches and scheduled work can authenticate without storing a second credential. A stolen active app token has a longer maximum lifetime, so encrypted device storage, TLS, revocation, session inventory, and prompt handling remain security requirements. Admin authentication keeps its 30-minute limit and still requires TOTP.
