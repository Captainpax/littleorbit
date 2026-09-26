# ADR 0010: First-party resumable APK delivery

- Status: Accepted
- Date: 2026-09-12

## Context

The first updater release used GitHub Releases for every APK transfer. A real Android download repeatedly stalled at 99 percent, leaving a signed build unavailable even though Little Orbit's website and API were healthy. The app already verifies APK bytes independently, so the transport host can change without weakening the update identity.

## Decision

Little Orbit serves each published phone APK from the exact versioned endpoint `/api/v1/releases/{version}/apk`. The API reads from an ignored, read-only Compose bind mount. It computes the full SHA-256 and checks the byte count against immutable database metadata before every response. Missing, changed, or corrupt bytes return a generic `503` and are never partially trusted.

The endpoint supports `GET`, `HEAD`, and HTTP byte ranges through `FileResponse`. Responses provide an exact content length, attachment filename, checksum header, strong digest-based ETag, and immutable caching. The download page always derives this first-party path from the published version instead of accepting an arbitrary metadata URL.

Android trusts the matching HTTPS endpoint on `lil-orb.pax-kun.com`. It temporarily retains the exact canonical GitHub release pattern for historical cached metadata. All existing size, SHA-256, package-name, increasing-version, and pinned-certificate checks remain mandatory before `PackageInstaller` opens.

GitHub Releases continue as a source-history and binary mirror. The operator copies and verifies local bytes before publishing metadata. Release files and signing secrets remain outside Git.

## Consequences

- Interrupted Android and browser downloads can resume against one stable origin.
- APK traffic now uses the home connection and appears in bounded gateway access logs.
- Public download availability depends on the Little Orbit host, NPM host, power, and internet connection.
- Release storage requires backup or reproducible restoration from the signed GitHub mirror.
- RC3 cannot trust the new authority, so RC3 users need one manual RC4 install from the website. RC4 and later can update from the API.
