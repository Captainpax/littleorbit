# ADR 0002: Little Orbit-owned authentication

- Status: Accepted
- Date: 2026-09-10

## Context

The service needs email verification, recovery, session revocation, two-person pairing, deletion, and owner TOTP without placing core access behind a paid identity provider.

## Decision

Use email/password accounts with Argon2id, opaque rotated sessions, hashed one-use verification/reset tokens, provider-neutral SMTP, and password-plus-TOTP administration. Encrypt TOTP secrets and hash recovery codes.

## Consequences

The project owns sensitive authentication code and must test enumeration resistance, timing, replay, expiry, rotation, throttling, and recovery carefully. No social login is required for 1.0.
