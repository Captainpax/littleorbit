# Little Orbit

[![CI](https://github.com/Captainpax/littleorbit/actions/workflows/ci.yml/badge.svg)](https://github.com/Captainpax/littleorbit/actions/workflows/ci.yml)

![Little Orbit logo concept](docs/assets/little-orbit-logo-concept.png)

Little Orbit is a free and open couples platform for staying curious, sharing small moments, and understanding each other better. It has no subscriptions, premium tiers, advertising, or sale of personal data. The project is also a practical learning space: important flows, privacy boundaries, and design decisions are documented in public.

> **Project status:** 1.0 release candidate. The implemented flows pass automated API, protocol, web, signed Android release, gateway, email, deletion, and backup-restore checks. Public HTTPS and the source-restricted Windows Firewall rule are live. Real-device photo, wireless-watch-install, privacy/permission testing, the DHCP reservation, and legal review remain launch gates, so do not use the public deployment for real relationship data yet.

## What 1.0 includes

- Five daily questions with private-until-both-answer reveal behavior.
- Single choice, multiple choice, free text, partner guessing, and weighted 1–5 prompts.
- Shared countdowns and plain-text live notes with offline drafts.
- A mutually accepted relationship start date, shown separately from nearby-time estimates.
- Estimated nearby time from mutually consented, accuracy-aware location samples.
- Android home widget, Wear OS tile, and watch complication with refresh and honest stale states.
- Private cropped profile photos for the couple planets on the phone and Wear launcher, with initials when a photo is absent.
- An in-app, phone-hosted wireless-debugging installer for the self-hosted Wear APK; no computer script or app store is required.
- A user-approved phone updater with resumable first-party downloads that verifies the APK hash, size, package, version, and pinned signing certificate before Android asks to install it.
- Eight-character, single-use pairing with confirmation.
- A public website for registration, account recovery, APK releases, privacy, and project documentation.
- Public patch notes at `/patch-notes` and a standards-based RSS feed at `/patch-notes.xml`.
- A privacy-limited owner console and local daily-question generation through Ollama.

![Implemented signed RC8 Android home](docs/assets/android-home-rc8-emulator.png)

## Architecture

Android, Wear OS, and browsers connect to `https://lil-orb.pax-kun.com`. Nginx Proxy Manager forwards traffic to a single gateway port on the application host. The gateway routes `/api/*` and `/ws/*` to FastAPI and all other paths to Next.js. PostgreSQL, Ollama, the worker, and Mailpit remain private to the Compose network.

See the [network and logic flows](docs/NETWORK-FLOW.md), [privacy design](docs/PRIVACY.md), and [architecture decisions](docs/adr/) before changing a trust boundary.

## Quick start

Requirements: Docker Desktop, Compose, Node.js 24+, Python 3.12 or 3.13, Java 17, and Android SDK 36 for Android builds.

```bash
copy .env.example .env
docker compose --env-file .env -f infra/compose.yaml -f infra/compose.dev.yaml up --build
```

Then open `http://localhost:8180`. Mailpit is available in the development profile at `http://localhost:8025`. The first Ollama model pull is large and may take several minutes. The base Compose file works on CPU; add `infra/compose.gpu.yaml` on a configured NVIDIA Docker Desktop host.

For direct development:

```bash
npm install --prefix apps/web
npm --prefix apps/web run dev
python -m venv .venv
.venv/Scripts/pip install -e services/api -e services/ai
.venv/Scripts/uvicorn little_orbit_api.main:app --reload --port 8000
```

## Signed Android release

[`1.0.0-rc.8`](https://github.com/Captainpax/littleorbit/releases/tag/v1.0.0-rc.8) is the current signed phone and Wear OS release candidate. The [phone APK](https://lil-orb.pax-kun.com/api/v1/releases/1.0.0-rc.8/apk) and [Wear APK](https://lil-orb.pax-kun.com/api/v1/releases/1.0.0-rc.8/wear-apk) are served by Little Orbit with byte-range resume support; GitHub keeps a release mirror, checksums, and source history. The phone SHA-256 is `a20947a885959f0201f7559052b272fcd1a7d4f3f6057029d49521627270d156`; the Wear SHA-256 is `de1b1e5af6b983b412e89e46702396bd5db027a0a689697c5f28d577b5ef723c`. RC8 refreshes the home hierarchy, adds private profile photos, moves Wear installation into the phone app, and publishes website patch notes with RSS. The updater and watch installer verify size, package, version, hash, and the [pinned signing certificate](docs/signing/README.md). This remains a test release until the real-device launch gate is complete.

## Privacy promise

Little Orbit collects only what a selected feature needs. AI question generation in 1.0 is site-wide and receives no couple data. Precise coordinates are kept for no more than 24 hours, administrator views exclude relationship content, and unpairing immediately stops sharing. Read the full [privacy design](docs/PRIVACY.md).

## Project documents

- [Showcase](SHOWCASE.md)
- [Contributing](CONTRIBUTING.md) and [contributors](CONTRIBUTORS.md)
- [Roadmap](ROADMAP.md)
- [Patch notes](https://lil-orb.pax-kun.com/patch-notes) and [RSS](https://lil-orb.pax-kun.com/patch-notes.xml)
- [Security policy](SECURITY.md)
- [Code of conduct](CODE_OF_CONDUCT.md)
- [Network flow](docs/NETWORK-FLOW.md)
- [Local development](docs/operations/LOCAL-DEVELOPMENT.md)
- [Deployment runbook](docs/operations/DEPLOYMENT.md)
- [Backup and restore](docs/operations/BACKUP-RESTORE.md)
- [Documentation map](docs/DOCUMENTATION-MAP.md)
- [Latest verification record](docs/operations/VERIFICATION-RC8-2026-09-12.md)

## License and support

The application code is licensed under the [MIT License](LICENSE). Optional donations may support hosting, but will never unlock features. Little Orbit hosts the primary signed phone APK; GitHub mirrors releases and remains the canonical source history.

Source, issues, and releases live at [github.com/Captainpax/littleorbit](https://github.com/Captainpax/littleorbit).
