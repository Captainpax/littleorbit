# ADR 0013: Private normalized account profile images

- Status: accepted
- Date: 2026-09-12

## Context

The concept art identifies each person as one planet. Initials work without personal data, but couples asked to choose profile photos for the phone and Wear launcher. Original image files can contain location metadata, oversized dimensions, animation, and encodings that are expensive or unsafe to serve. A profile image also outlives a pairing, while partner authorization must end as soon as a pairing ends.

## Decision

Treat the image as account-level private data. The phone obtains a user-approved square crop and uploads at most 5 MiB. The API accepts JPEG, PNG, or WebP, decodes at most 20 million pixels, rejects animation, applies orientation, converts to RGB, and produces metadata-free 512-pixel and 128-pixel WebP variants. It stores only those variants, hashes, a revision, and an update instant in PostgreSQL.

Only the owner can replace, delete, or fetch the owner's image. The current partner may fetch the 128-pixel variant only after active-pair authorization. Account deletion cascades to the image, unpairing removes partner access immediately, and relationship archives do not copy it. The account export includes the owner's processed image.

Serialize replacement and deletion by locking the owning account even when the image row does not exist. Clients compare the content hash as well as the revision before reusing encrypted cached bytes. Phone and Wear launcher caches are private; widget, tile, and complication caches remain text-only. Admin APIs and views expose no image content.

## Consequences

The system never preserves the original upload or its metadata. WebP support and image bounds are now release dependencies and need malformed-image tests. Database backups contain private processed photos and inherit the database backup controls. A partner may retain an encrypted cached thumbnail while offline, so unpair and sign-out flows must clear it locally as soon as that state reaches the device.
