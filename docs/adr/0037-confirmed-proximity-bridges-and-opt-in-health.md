# ADR 0037: Confirmed proximity bridges and opt-in collection health

- Status: accepted
- Date: 2026-09-19

## Context

The five-minute chronological estimator prevented unsupported credit, but production-safe aggregates showed uneven phone collection: one stream often arrived around 15 minutes apart. Two days of physical proximity could therefore contain long unverified gaps even when later evidence again placed both phones nearby. Same Wi-Fi cannot prove the people are together and would introduce network identifiers that Little Orbit does not need.

## Decision

Direct observed intervals retain the five-minute sample-skew and interval bounds from ADR 0036. A later strong nearby anchor may confirm the gap after a previous strong nearby anchor when it arrives within 20 minutes and no intervening chronological observation reports apart or poor accuracy. Until the later anchor arrives, the gap remains unverified and contributes zero durable seconds. Confirmed gap seconds are stored separately from observed seconds in coordinate-free minute buckets.

The five-minute live projection is unchanged. Its deadline still depends on fresh evidence from both members. A network restoration or Wi-Fi/cellular transition may ask Android for a new fix and upload retry, but network identity is neither persisted nor sent to the API.

History uses the couple's IANA home timezone. Retained minute buckets carry observed, bridged, unverified, apart, and poor-accuracy components for 30 days; day boundaries therefore respect 23- and 25-hour daylight-saving days. Audited corrections continue to win over automatic totals. Older totals without safely repartitionable evidence remain labeled legacy or mixed.

Each Android installation may separately opt into a latest-only collection-health snapshot. It contains model, battery/charging, network transport category, permission and battery-restriction state, tracking-notification state, upload state, queue size, and last check-in. The active partner may read it without an installation identifier. It expires in 24 hours, is deleted on opt-out or unpair, has no admin route, and is excluded from backups.

## Consequences

The estimate recovers bounded time after ordinary OEM collection gaps without turning Wi-Fi or a lone phone into proximity proof. Timeline provenance makes the uncertainty visible. Health sharing can reveal device metadata to a partner, so it is disabled by default and short-lived. Raw coordinates still expire within 24 hours and remain outside backups.

This decision supersedes ADR 0036 only for intervals longer than five minutes. ADR 0036 remains authoritative for chronological evaluation, mutual freshness, live projection, raw-coordinate handling, and passive surfaces.
