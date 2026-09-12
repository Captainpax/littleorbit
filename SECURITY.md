# Security policy

## Reporting a vulnerability

Do not publish an issue containing an exploitable vulnerability, credential, personal data, or production detail. Contact the repository owner privately through the security advisory feature on GitHub. Include affected versions, reproduction steps, impact, and any suggested mitigation. Please allow time to investigate before public disclosure.

## Supported versions

Until 1.0, only the current default branch receives security fixes. After 1.0, the latest minor release will be supported unless a release note says otherwise.

## Security boundaries

The public gateway is the only exposed container port. Authentication does not imply authorization to a couple resource. AI is isolated from relationship data. Admin views exclude relationship content and profile images. Tokens and recovery codes are stored only as hashes; TOTP secrets, Android profile thumbnails, and the phone's reusable wireless-ADB private key are encrypted at rest. Server profile images are normalized to bounded metadata-free WebP variants and are available only to the owner and current partner. Precise coordinates expire within 24 hours.

The in-app Wear installer accepts APK metadata only from the exact first-party versioned HTTPS route and verifies byte count, SHA-256, package name, version code, required watch feature, and the pinned signing certificate. It blocks phones and downgrades. A watch security patch older than May 1, 2026, or an unreadable patch level produces a warning that requires an explicit choice before installation. Wireless debugging should be disabled on the watch after setup.

Never use development keys or Mailpit in a public deployment. Follow the deployment and backup runbooks and verify restore behavior before serving real users.
