# ADR 0042: Device-bound Big Orbit administration

Status: accepted

Date: 2026-09-20

## Context

The browser owner console mixed public-site delivery with privileged operations. A copied administrator bearer token could be replayed from another client, and browser routes could not provide the focused notifications and action workflow wanted for routine ownership.

## Decision

The public Next.js application no longer contains an administrator interface. Privileged operations move to a separate open-source Android application, Big Orbit, in the `Captainpax/big-orbit` repository. Little Orbit exposes the administration contract only under `/v2/admin`; `/v1/admin` is removed after the enrollment cutover.

Big Orbit is Java 17/XML with package `com.littleorbit.bigorbit`. Its independent signing identity is not trusted as a Little Orbit or Wear update. Enrollment combines the existing administrator password and replay-safe MFA proof with a P-256 Android Keystore public key. A five-minute signed challenge proves key possession. The resulting random device credential expires after 90 days and is stored with the private key and short administrator session in Android-protected storage. Every 30-minute session is bound server-side to the enrolled device and can be revoked independently.

The app exposes an action inbox, operational health, thresholded quiz intelligence, AI provenance, typed jobs, backup/restore evidence, enrolled devices, and generic local notifications. Job requests select only a fixed kind and an optional Monday date; they cannot carry commands, SQL, paths, or arbitrary arguments. Alert acknowledgement belongs to one enrolled installation.

During deployment, an owner may temporarily run a build that accepts both the existing proof and device enrollment. After at least one Big Orbit device is verified and a recovery path is recorded, the final application removes `/v1/admin` and the public `/admin` pages together. The repository contains only the final `/v2/admin` state.

## Consequences

- Losing a device does not require trusting a browser cookie; another enrolled device can revoke it.
- Initial enrollment still requires a verified administrator account, password, and current TOTP or unused recovery proof.
- Big Orbit notifications contain operational wording only and use the authenticated Little Orbit HTTPS API plus Android scheduling; no hosted push service is introduced.
- Browser automation and bookmarks for `/admin` intentionally fail with 404 after cutover.
- Little Orbit and Big Orbit release keys, application IDs, artifacts, and update channels remain separate.
