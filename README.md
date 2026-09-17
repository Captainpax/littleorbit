# Little Orbit

[![CI](https://github.com/Captainpax/littleorbit/actions/workflows/ci.yml/badge.svg)](https://github.com/Captainpax/littleorbit/actions/workflows/ci.yml)

![Little Orbit logo concept](docs/assets/little-orbit-logo-concept.png)

Little Orbit is a free and open couples platform for staying curious, sharing small moments, and understanding each other better. It has no subscriptions, premium tiers, advertising, or sale of personal data. The project is also a practical learning space: important flows, privacy boundaries, and design decisions are documented in public.

> **Project status:** 1.0 stable release. Together Time now evaluates every chronological observation, requires current evidence from both phones, and gives the foreground phone only a five-minute server-bounded live projection. Widget and Wear surfaces stay on authoritative observed nearby time. Partner alerts remain entirely on Little Orbit's authenticated WebSocket and HTTPS paths, with no hosted push provider. Long-term two-phone battery and OEM reliability measurements continue as 1.x work.

## What 1.0 includes

- Five daily questions with private-until-both-answer reveal behavior.
- Single choice, multiple choice, free text, partner guessing, and weighted 1–5 prompts.
- Calendar-style timed or all-day countdowns with private reminder choices, upcoming/past views, one-way Android calendar export, encrypted offline edits, and partner change alerts.
- A preview-first Markdown workspace with live presence, cursor-stable synchronization, inline private images and GIFs, drafts, search, archives, and seven-day undo.
- Couple-authorized image, PDF, text, audio, and video attachments with resumable upload, malware scanning, metadata removal, verified private previews, optional offline copies, deletion, a 100 MiB file limit, and a 2 GiB couple quota.
- A content-free 30-day activity panel for note, attachment, countdown, quiz, and Smooch events, with a private seen position for each partner.
- Responsive Android navigation: a hamburger or left-edge swipe opens the drawer on phones, a bounded persistent rail stays visible on wide screens, and the right action panel appears only when the current screen has actions.
- Independent Home, Settings, and App updates destinations with a visible current-location state and guest-safe navigation filtering.
- Estimated nearby time from mutually consented, accuracy-aware chronological evidence, with freshness supported by both phones. The detail screen animates seconds only through a short server deadline; passive surfaces never extrapolate. The confirmed pairing instant remains relationship metadata and is not presented as measured time spent together.
- A dedicated Smooch tab using nine fixed emoji, a five-per-hour sender limit, orbit-pulse confirmation, per-device notifications, weekly totals, and retained history.
- Optional account-synced partner alerts for Smooches, the first document edit, countdown changes, daily quiz availability, partner completion, and shared results, with generic lock-screen text, independent delivery to each installation, authenticated first-party foreground hints, immediate opt-out cleanup, and self-hosted background polling. Android may delay background checks under Doze or manufacturer battery rules.
- Android home widget, Wear OS launcher, tile, and watch complication led by estimated nearby duration with honest fresh, stale, and unavailable states. The widget selects a compact layout when vertically resized. Relationship-scoped generations purge every surface on sign-out, unpair, or inactive pairing; a disconnected watch deletes its cache after 24 hours.
- Private cropped relationship avatars for the couple planets on the phone and Wear launcher. Each person chooses only their partner's picture; initials remain when a photo is absent.
- An in-app, phone-hosted wireless-debugging installer for the self-hosted Wear APK, with automatic or explicit manual endpoint selection, transient pairing codes, verified-download retry, and installed-version detection; no computer script or app store is required.
- An opt-in update detector that checks metadata every six hours and presents a once-per-launch update prompt; APK download and Android installation still require explicit approval and full verification.
- Eight-character, single-use pairing with confirmation.
- A public website for registration, account recovery, APK releases, privacy, and project documentation.
- Public patch notes at `/patch-notes` and a standards-based RSS feed at `/patch-notes.xml`.
- A privacy-limited owner console and local daily-question generation through Ollama.

![Implemented RC13 countdown timeline on a wide Android emulator](docs/assets/android-countdowns-rc13-tablet.png)

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

[`1.0.0`](https://github.com/Captainpax/littleorbit/releases/tag/v1.0.0) is the current signed stable release. The [phone APK](https://lil-orb.pax-kun.com/api/v1/releases/1.0.0/apk) is 36,246,289 bytes with SHA-256 `741349a13e976e2f9396562a424161bcc857abe65d5948f4f64068dd756ae398`. The independently versioned 14,189,878-byte [Wear APK](https://lil-orb.pax-kun.com/api/v1/releases/1.0.0/wear-apk) is version code 18 with SHA-256 `4fdb58ab94b7912a72910d2a6163be648102992893d515bd4662d3f880c1e159`. Both artifacts retain the pinned [signing certificate](docs/signing/README.md). GitHub remains the canonical source history while APK bytes are served by Little Orbit's first-party API. Notifications are fully self-hosted; a visible app receives authenticated WebSocket hints and background WorkManager polls the same API, subject to Android battery delays. RC10.1 and RC11.1 require one manual update because their already-installed updater abandons its package session; automatic updates work after crossing that boundary.

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
- [Latest verification record](docs/operations/VERIFICATION-1.0.0-2026-09-16.md)

## License and support

The application code is licensed under the [MIT License](LICENSE). Optional donations may support hosting, but will never unlock features. Little Orbit hosts the primary signed phone APK; GitHub mirrors releases and remains the canonical source history.

Source, issues, and releases live at [github.com/Captainpax/littleorbit](https://github.com/Captainpax/littleorbit).
