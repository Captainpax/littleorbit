# ADR 0014: Phone-hosted self-hosted Wear installation

- Status: accepted
- Date: 2026-09-12
- Supersedes: the computer-installer portion of ADR 0012

## Context

Little Orbit does not depend on Google Play, and the PowerShell wireless-ADB guide used for RC6 and RC7 made a normal watch install depend on a computer. The phone already verifies signed release metadata and can reach a watch on the same local network, but wireless ADB is a sensitive local capability and published Android libraries do not share Little Orbit's Java 17 source target.

## Decision

Put an explicit installation wizard in the phone app. It downloads the current Wear artifact only from the exact versioned Little Orbit HTTPS endpoint, checks size, SHA-256, package, version, required watch feature, and the pinned release certificate before any watch connection, then discovers Android pairing and TLS endpoints with DNS-SD. Manual host and ports remain available when discovery is denied or unavailable.

The person enters the watch's short-lived six-digit pairing code. The phone creates one ADB identity, encrypts its private key with Android Keystore-backed storage, and may reuse it for later updates. The wizard reads only model, SDK, build characteristic, installed Little Orbit version, and security-patch date. It rejects non-watch devices, unsupported SDKs, and downgrades. A missing or older-than-May-1-2026 security patch produces a warning with cancel and explicit continue choices. Installation uses package-manager replace without downgrade flags.

Kadb 2.1.1 is confined to `KadbWatchClient`. Its Android artifact targets Java 21 bytecode and compileSdk 36, so the Java 17 application calls its small audited surface through reflection while D8 packages it. Version 2.1.2 and later currently require compileSdk 37. Any dependency upgrade requires renewed bytecode, manifest, license, and physical-device review.

## Consequences

The common install path needs only a phone and watch on trusted Wi-Fi, but the person must enable Wear OS developer options and wireless debugging. They should disable wireless debugging afterward. The app exposes **Forget watch authorization**, and app-data removal also removes the identity. Physical phone/watch pairing remains a release gate because emulators and unit tests cannot prove OEM wireless-debugging behavior.
