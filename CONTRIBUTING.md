# Contributing to Little Orbit

Thank you for helping build a free couples app. Treat relationship and location data with care, explain non-obvious decisions, and keep discussion respectful.

## Setup

1. Install Docker Desktop, Node.js 24+, Python 3.12+, Java 17, and Android SDK 37.
2. Copy `.env.example` to `.env` and replace development values.
3. Start the local stack with `docker compose -f infra/compose.yaml -f infra/compose.dev.yaml up --build`.
4. Read the root `AGENTS.md`, then the closest nested guide for the code you will change.

## Standards

- Keep public Java APIs documented with Javadoc and Python public modules and callables documented with docstrings.
- Use strict TypeScript and explicit schemas at network boundaries.
- Keep functions below 60 logical lines, files below 500, and cyclomatic complexity at or below 10.
- Add comments for concurrency, privacy guarantees, algorithms, platform workarounds, and unusual invariants.
- Use UTC for stored instants and explicit IANA time zones for user-facing dates.
- Never commit secrets, production data, signed keys, profile images, or private exports.
- Publish Android metadata only from the signed build's `release-manifest.json`; never copy a phone version code into the Wear field by assumption.
- Inventory every repository-owned Markdown file for each update. Update or create every affected public, protocol, architecture, privacy, operations, release, and contributor document, and always review `ROADMAP.md`.

## Changes and pull requests

Open an issue for broad feature or privacy changes. Keep pull requests focused, describe the concrete behavior, add the smallest meaningful tests, and update the matching public documents and diagrams. Use [`docs/DOCUMENTATION-MAP.md`](docs/DOCUMENTATION-MAP.md) to complete the inventory. Durable architectural decisions need a numbered ADR.

Before requesting review, run the commands in the closest `AGENTS.md`. Include the checks you actually ran and any device, GPU, browser, or production check that remains outstanding.

Protocol changes must add versioned valid and invalid fixtures. Security or privacy fixes should follow the private reporting process in `SECURITY.md` rather than starting with a public issue.

Attachment work must exercise both the JSON contract and private bytes. Use synthetic fixtures, preserve the authorization-before-lookup order, bound streams before buffering, and verify that scanner failures leave bytes unavailable. Changes to supported types or storage must update the privacy, security, network, backup, deployment, third-party, release, and roadmap documents in the same pull request.

## Isolated Android smoke testing

Use the disposable smoke stack for paired-account Android checks. It keeps test users, mail, attachments, and database rows outside the hosted volumes.

```powershell
.\infra\scripts\smoke-stack.ps1 up
.\infra\scripts\android-smoke.ps1 -Serial emulator-5554 -AccountIndex 0 -ResetApp
.\infra\scripts\smoke-stack.ps1 down
```

Run the Android script once per supported emulator serial. The harness creates only `@example.com` accounts, verifies them through the isolated Mailpit inbox, pairs exactly two accounts, and writes its ignored credentials under `.inspect/`. Never point the harness at the hosted gateway or reuse a real account.
