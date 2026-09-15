# ADR 0034: Fully self-hosted notifications

- **Status:** Accepted
- **Date:** 2026-09-15
- **Supersedes:** ADR 0027

## Context

Little Orbit is intended to be self-hosted end to end. ADR 0022 established PostgreSQL delivery rows, random installation identifiers, authenticated foreground WebSocket hints, and Android polling as the notification source of truth. ADR 0027 later allowed an optional Firebase wake signal. Even without production credentials, that SDK, server sender, provider address storage, and configuration created an external dependency and a privacy and supply-chain surface that conflicts with the product boundary.

Android does not provide a general background socket that a self-hosted server can wake silently and reliably. WorkManager has a 15-minute minimum periodic interval and may run later under Doze or manufacturer battery policy. An always-running foreground service could reduce that delay, but it would require a permanent notification and measurable battery use.

## Decision

Little Orbit uses only its own authenticated HTTPS and WSS endpoints for partner alerts. PostgreSQL stores short-lived notification events and one delivery row for each active random installation identifier. While Little Orbit is visible, an authenticated WSS connection receives only `notification.available`, then fetches authorized event metadata over HTTPS. When the app is backgrounded, WorkManager polls the same pending-event endpoint. Android creates the local private notification and acknowledges an event only after that installation accepts the post.

The Android build contains no Firebase Messaging or hosted-notification SDK, manifest component, project identifier, provider address, or recovery state. Upgrade initialization deletes the four retired Little Orbit address and recovery preferences used by the published RC14 path. The API stores no provider address and performs no notification-provider egress. During the RC14-to-RC15 transition, the device heartbeat accepts only a legacy `push_token: null` field and always reports `push_enabled: false`; any non-null address fails validation. That null-only wire shim can be removed after the minimum supported client is RC15.

Foreground alerts are near-real-time when the first-party socket is connected. Background alerts are eventual and may arrive later than the nominal 15-minute interval. Product text and release verification must state that limit. A persistent foreground transport or a separate self-hosted distributor requires a new architecture, privacy, battery, and abuse review.

## Consequences

- No notification request, identifier, or timing signal is sent to a hosted push provider.
- The server, database, Compose configuration, and signed APK have less credential and dependency surface.
- Multi-installation acknowledgement, content minimization, authorization, category preferences, and unpair cleanup remain unchanged.
- Background Smooch, quiz, countdown, document, and correction alerts may be delayed by Android power management.
