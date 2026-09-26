# ADR 0023: Partner-assigned relationship avatars

- Status: accepted for RC13
- Date: 2026-09-13

## Context

Account-owned profile photos let a person choose their own picture, which does not match Little Orbit's intended shared ritual. A replacement must prevent self-assignment, keep old relationship media from following an account into a later pairing, and preserve the rule that administrators cannot browse couple images.

## Decision

An avatar belongs to one active relationship and one subject account. Only the other current member may create, replace, or delete it. The API authorizes current membership before looking up an avatar, locks the relationship during replacement, rejects `subject_account_id == assigned_by_account_id`, and produces bounded metadata-free WebP variants with a monotonic revision.

Android presents the signed-in person's avatar as read-only and labels it as chosen by their partner. The choose, crop, and remove controls apply only to the partner's avatar. Phone cache publication can send both authorized thumbnails to the Wear launcher; passive widget, tile, and complication surfaces remain text-only.

Migration `0016` deliberately deletes the old account-owned photo rows because their ownership meaning cannot be converted honestly. Unpairing deletes both relationship avatars immediately. Account deletion removes any relationship avatar in which the account was the subject or assigner. Avatars are excluded from relationship archives and never transfer to a later partner.

## Consequences

- A person cannot set or silently replace their own avatar.
- Existing self-selected photos disappear once at the RC13 migration boundary and can be chosen again by the partner.
- Every read and write remains limited to the active couple; the owner console has no image endpoint or viewer.
- Re-pairing begins with initials and an empty relationship-scoped avatar set.
