# Security policy

## Reporting a vulnerability

Do not publish an issue containing an exploitable vulnerability, credential, personal data, or production detail. Contact the repository owner privately through the security advisory feature on GitHub. Include affected versions, reproduction steps, impact, and any suggested mitigation. Please allow time to investigate before public disclosure.

## Supported versions

Until 1.0, only the current default branch receives security fixes. After 1.0, the latest minor release will be supported unless a release note says otherwise.

## Security boundaries

The public gateway is the only exposed container port. Authentication does not imply authorization to a couple resource. AI is isolated from relationship data. Admin views exclude relationship content, attachment names and bytes, and profile images. Tokens and recovery codes are stored only as hashes; TOTP secrets, Android profile thumbnails, queued Smooches, kept-offline note attachments, and the phone's reusable wireless-ADB private key stay in protected or app-private storage. Smooch creation is transactionally rate-limited to five sends per account in a rolling hour, and account deletion erases the old relationship history. Server profile images are normalized to bounded metadata-free WebP variants and are available only to the owner and current partner. Precise coordinates expire within 24 hours.

Note attachments require current couple authorization before note or file lookup. Server-generated storage keys prevent path selection, request streams and chunks are bounded, exact offsets prevent gaps and overwrite races, and an operation ID can resume only the same declared bytes. Unscanned content is never downloadable. ClamAV runs on an internal-only network and scanner outages fail closed; images, PDFs, audio, and video are re-encoded or remuxed without source metadata before availability. The Android client verifies the sanitized SHA-256 digest before previewing or retaining an offline copy. File deletion and expired-note cleanup remove private volume bytes.

The in-app Wear installer accepts APK metadata only from the exact first-party versioned HTTPS route and verifies byte count, SHA-256, package name, version code, required watch feature, and the pinned signing certificate. It associates DNS-SD results with the discovered host and network, removes lost services, refreshes the post-pair connection port, and retries only bounded TLS transitions. It proves authorization with a harmless ADB command before reading privacy-safe compatibility properties. It blocks phones and downgrades. Pairing uses bundled public Conscrypt APIs; hidden-API bypass code is excluded. Safe diagnostic codes never retain pairing codes, endpoints, fingerprints, or raw transport errors. A watch security patch older than May 1, 2026, or an unreadable patch level produces a warning that requires an explicit choice before installation. Wireless debugging should be disabled on the watch after setup.

Automatic update work retrieves signed release metadata only. It never downloads APK bytes or opens Android's installer without a person's explicit action. Required compatibility floors may bypass the optional check preference, but every candidate still passes origin, byte-count, checksum, package, version, and signer validation.

Never use development keys or Mailpit in a public deployment. Follow the deployment and backup runbooks and verify restore behavior before serving real users.
