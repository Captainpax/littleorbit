# Security policy

## Reporting a vulnerability

Do not publish an issue containing an exploitable vulnerability, credential, personal data, or production detail. Contact the repository owner privately through the security advisory feature on GitHub. Include affected versions, reproduction steps, impact, and any suggested mitigation. Please allow time to investigate before public disclosure.

## Supported versions

Until 1.0, only the current default branch receives security fixes. After 1.0, the latest minor release will be supported unless a release note says otherwise.

## Security boundaries

The public gateway is the only exposed container port. Authentication does not imply authorization to a couple resource. AI is isolated from relationship data. Admin views exclude relationship content. Tokens and recovery codes are stored only as hashes; TOTP secrets are encrypted. Precise coordinates expire within 24 hours.

Never use development keys or Mailpit in a public deployment. Follow the deployment and backup runbooks and verify restore behavior before serving real users.
