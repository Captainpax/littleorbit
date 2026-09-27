# ADR 0046: Terminal PIN bootstrap for Big Orbit devices

Status: accepted

Date: 2026-09-23

## Context

Big Orbit 1.2 required an already configured MFA proof while enrolling its first device. That created a circular and confusing first-owner flow, while treating device enrollment as an ordinary password/MFA login made it too easy to mistake a copied bearer for proof of a particular Android device.

## Decision

An owner starts every new Big Orbit device from the Little Orbit server console with `bootstrap-admin <email>`. The command verifies an active administrator and prints one cryptographically generated eight-digit PIN once. PostgreSQL stores only a domain-separated hash. The PIN expires after ten minutes, permits five failed attempts, is consumed once, and replaces every earlier unused PIN and unfinished bootstrap for that administrator.

The fresh Big Orbit device submits the administrator email, password, PIN, a label, and its newly created P-256 public key. A valid request consumes the PIN before returning a separate ten-minute restricted setup token. That token can call only bootstrap status, device challenge/proof, and first-MFA confirmation routes; it is never accepted by ordinary `/v2/admin` metadata or operation routes. Process death may resume the capability until expiry.

The app proves possession of the Android Keystore key with a single-use, purpose-separated challenge. If the owner has no enabled MFA factor, the server stages a TOTP secret and returns an authenticator URI plus a server-rendered QR image. The app protects the screen from capture, confirms one six-digit code, shows recovery codes once, then approves the device and issues the ordinary device credential and short session. If MFA already exists, its secret and recovery codes are unchanged; successful key proof approves the device directly.

Passwords, PINs, setup tokens, TOTP secrets, recovery codes, device credentials, and signatures are excluded from logs and audit metadata. Pending devices are revoked when setup expires, and stale bootstrap rows are purged. The public web app remains outside the flow.

## Consequences

- A new device needs brief access to the trusted server console as well as the administrator password.
- A stolen password alone, an observed PIN alone, or an unproved public key cannot create an administrator session.
- Regenerating a PIN deliberately expires every older live setup capability for that owner.
- A lost final response is recoverable only within the original ten-minute capability: the same device must sign a fresh challenge before the server rotates replacement credentials.
- Existing enrolled devices keep password plus current MFA login and independent revocation behavior.
- Recovery still depends on protected server access and the separately backed-up Big Orbit signing and administrator recovery material.
