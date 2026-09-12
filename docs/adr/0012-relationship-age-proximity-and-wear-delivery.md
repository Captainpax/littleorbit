# ADR 0012: Separate relationship age, nearby estimates, and Wear delivery

- Status: accepted
- Date: 2026-09-12

## Context

The original together-time value mixed two different ideas: the calendar age of a relationship and time inferred from background location. That made a new pair appear to have been together for zero days and hid the uncertainty of location processing. The watch app also needed a trustworthy self-hosted installation path because Little Orbit is not distributed through Play Store.

## Decision

Store the relationship start as a date that one partner proposes and the other accepts. Mutations use idempotent operation IDs, one pending proposal per couple, row locking, role-specific decisions, and a seven-day expiry. Keep the accepted date separate from location-derived nearby time in the API, Room, widget, Wear Data Layer, tile, and complication.

Nearby time remains an estimate. The server matches each partner's samples one-to-one within ten minutes, counts only consecutive confident pairs no more than twenty minutes apart, writes coordinate-free UTC-minute buckets, and recomputes the rolling raw-data window. Raw coordinates still expire within 24 hours. Either location opt-out deletes both partners' raw samples immediately on the server.

Publish phone and Wear APKs as distinct immutable first-party artifacts in one release record. The phone may detect whether the connected watch advertises Little Orbit, but Android does not silently sideload an APK to a watch. The More screen opens a guided wireless-ADB installer that verifies the exact endpoint, size, hash, package, version code, and pinned signing certificate before installation.

## Consequences

The relationship headline no longer depends on location permission or sampling quality. People must agree before changing their shared start date. Widgets and Wear surfaces need a versioned cache migration and explicit stale state. Self-hosted watch installation requires a computer and Wear OS wireless debugging until a trusted store or signed desktop installer is available.
