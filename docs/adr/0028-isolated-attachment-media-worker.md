# ADR 0028: Isolated attachment media worker

- **Status:** Accepted for RC14
- **Date:** 2026-09-14

## Context

An attachment is untrusted input that may exercise image, PDF, audio, or video parsers. Processing it inside the public API would combine account access, outbound network access, request handling, and complex codecs in one trust boundary. A clean malware scan alone also does not remove metadata, auxiliary streams, malformed structures, or decompression risks.

## Decision

The API accepts only allow-listed metadata, reserves quota transactionally, and streams exact-offset bounded chunks into a private staging volume. It never serves staging or processing bytes. A separate unprivileged media worker claims leased attachment jobs through a restricted database role, detects file type from the signature, scans through internal-only ClamAV, and rebuilds or explicitly transcodes accepted content. Images are re-encoded, PDFs are rasterized into clean pages, text is validated, and selected audio/video streams are transcoded without metadata or auxiliary streams.

The worker has a read-only root filesystem, dropped Linux capabilities, `no-new-privileges`, bounded CPU, memory, process count, and temporary storage. It joins only the internal media network with PostgreSQL and ClamAV and has no outbound network route. Publication is atomic only after the final byte count, sanitized digest, duration/page limits, and locked couple/global quota all pass. Failed, expired, abandoned, or orphaned jobs remain unavailable and are retried or deleted by bounded maintenance.

Clients authorize the current or former relationship before lookup and verify the advertised sanitized size and SHA-256 before preview or offline retention. Former-pairing access is read-only and exposes only attachments that reached the clean `available` state.

## Consequences

- A parser compromise has fewer credentials, syscalls, resources, and network paths available.
- Scanning or sanitization outages delay availability rather than exposing original bytes.
- Some valid but unsupported or unusually complex files are rejected instead of repaired silently.
- Database and attachment backups must be coordinated because metadata and sanitized bytes are separate state.
