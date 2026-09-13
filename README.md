# Little Orbit

[![CI](https://github.com/Captainpax/littleorbit/actions/workflows/ci.yml/badge.svg)](https://github.com/Captainpax/littleorbit/actions/workflows/ci.yml)

![Little Orbit logo concept](docs/assets/little-orbit-logo-concept.png)

Little Orbit is a free and open couples platform for staying curious, sharing small moments, and understanding each other better. It has no subscriptions, premium tiers, advertising, or sale of personal data. The project is also a practical learning space: important flows, privacy boundaries, and design decisions are documented in public.

> **Project status:** 1.0 release candidate. RC12.1 makes shared documents preview-first with verified inline private images, adds self-hosted per-device Smooch and document-edit notifications, and applies consistent reduced-motion-aware cosmic transitions. The complete two-physical-phone, battery, privacy/permission, DHCP-reservation, restore, and legal review gates remain open, so do not use the public deployment for real relationship data yet.

## What 1.0 includes

- Five daily questions with private-until-both-answer reveal behavior.
- Single choice, multiple choice, free text, partner guessing, and weighted 1–5 prompts.
- Shared countdowns and a preview-first Markdown workspace with live presence, cursor-stable synchronization, inline private images and GIFs, drafts, search, archives, and seven-day undo.
- Couple-authorized image, PDF, text, audio, and video attachments with resumable upload, malware scanning, metadata removal, verified private previews, optional offline copies, deletion, a 100 MiB file limit, and a 2 GiB couple quota.
- A content-free 30-day activity panel for note, attachment, countdown, quiz, and Smooch events, with a private seen position for each partner.
- Responsive Android navigation: a left drawer on phones, a persistent rail on wide screens, and a right action panel that follows the current screen.
- Relationship age beginning automatically at the couple's confirmed pairing instant.
- Estimated nearby time from mutually consented, accuracy-aware location samples.
- A dedicated Smooch tab using nine fixed emoji, a five-per-hour sender limit, orbit-pulse confirmation, per-device notifications, weekly totals, and retained history.
- Optional account-synced partner alerts for Smooches and the first document edit, with generic lock-screen text, channel controls, a content-free foreground hint, and durable background polling.
- Android home widget, Wear OS tile, and watch complication with refresh and honest stale states.
- Private cropped profile photos for the couple planets on the phone and Wear launcher, with initials when a photo is absent.
- An in-app, phone-hosted wireless-debugging installer for the self-hosted Wear APK; no computer script or app store is required.
- An opt-in update detector that checks metadata every six hours and presents a once-per-launch update prompt; APK download and Android installation still require explicit approval and full verification.
- Eight-character, single-use pairing with confirmation.
- A public website for registration, account recovery, APK releases, privacy, and project documentation.
- Public patch notes at `/patch-notes` and a standards-based RSS feed at `/patch-notes.xml`.
- A privacy-limited owner console and local daily-question generation through Ollama.

![Implemented signed RC8 Android home](docs/assets/android-home-rc8-emulator.png)

## Architecture

Android, Wear OS, and browsers connect to `https://lil-orb.pax-kun.com`. Nginx Proxy Manager forwards traffic to a single gateway port on the application host. The gateway routes `/api/*` and `/ws/*` to FastAPI and all other paths to Next.js. PostgreSQL, Ollama, the worker, and Mailpit remain private to the Compose network.

See the [network and logic flows](docs/NETWORK-FLOW.md), [privacy design](docs/PRIVACY.md), and [architecture decisions](docs/adr/) before changing a trust boundary.

## Quick start

Requirements: Docker Desktop, Compose, Node.js 24+, Python 3.12 or 3.13, Java 17, and Android SDK 37 for Android builds.

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

[`1.0.0-rc.12.1`](https://github.com/Captainpax/littleorbit/releases/tag/v1.0.0-rc.12.1) is the current signed release candidate. The [phone APK](https://lil-orb.pax-kun.com/api/v1/releases/1.0.0-rc.12.1/apk) is 35,938,870 bytes with SHA-256 `df104a03b9572f186236d686b42bf170365a2806907721cb35949ac108c9060d`. RC12.1 reuses the exact immutable 14,133,466-byte [RC12 Wear APK](https://lil-orb.pax-kun.com/api/v1/releases/1.0.0-rc.12.1/wear-apk), version code 15 and SHA-256 `9227bbb70ecf127a36a70d3f33101938df35f4b4cf62d80b71ff4a653a1c1868`, because no Wear code changed. Both artifacts retain the pinned [signing certificate](docs/signing/README.md), and GitHub mirrors the exact files and source history. RC10.1 and RC11.1 require one manual update because their already-installed updater abandons its package session; automatic updates work after crossing that boundary. This remains a test release until the complete real-device launch gate passes.

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
- [Latest verification record](docs/operations/VERIFICATION-RC12.1-2026-09-13.md)

## License and support

The application code is licensed under the [MIT License](LICENSE). Optional donations may support hosting, but will never unlock features. Little Orbit hosts the primary signed phone APK; GitHub mirrors releases and remains the canonical source history.

Source, issues, and releases live at [github.com/Captainpax/littleorbit](https://github.com/Captainpax/littleorbit).
