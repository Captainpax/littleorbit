# Little Orbit

[![CI](https://github.com/Captainpax/littleorbit/actions/workflows/ci.yml/badge.svg)](https://github.com/Captainpax/littleorbit/actions/workflows/ci.yml)

![Little Orbit logo concept](docs/assets/little-orbit-logo-concept.png)

Little Orbit is a free and open couples platform for staying curious, sharing small moments, and understanding each other better. It has no subscriptions, premium tiers, advertising, or sale of personal data. The project is also a practical learning space: important flows, privacy boundaries, and design decisions are documented in public.

> **Project status:** [1.3.0](https://github.com/Captainpax/littleorbit/releases/tag/v1.3.0) is the current signed stable release. It adds themed local-time weekly quizzes, reviewed Markdown retrieval, a 2,190-question one-use reserve, strict semantic no-repeat gates, richer Big Orbit observability, and terminal-PIN device bootstrap. Partner alerts remain entirely self-hosted.
>
> **Release policy:** 1.3.0 is optional (phone code 29, Wear code 21), keeps the compatibility floor at phone code 23, and has no forced-update deadline. The exact phone, Wear, and Big Orbit APKs were independently inspected and cold-launched on API 36/API 34 emulators. The owner explicitly deferred physical phone/watch, two-partner, and fresh/returning Big Orbit observations to live QA; that missing evidence remains visible in the verification records.
>
> **Big Orbit:** [Big Orbit 1.3.0](https://github.com/Captainpax/big-orbit/releases/tag/v1.3.0) is the matching published owner app. It retains its own package and independent signer while sharing the 1.3.0 release-train label and one-use terminal-PIN enrollment flow.

The 1.1.0 watch update is signed as phone code 25 and Wear code 19. Watch records are scoped to the selected target and a monotonic purge generation, watch-originated actions contain no account credential, and the phone revalidates the selected watch and active relationship before accepting them. The owner explicitly approved release without the unavailable physical Wear-device gate; that missing evidence remains visible in the verification record.

## What the current source includes

- Five daily questions with private-until-both-answer reveal behavior.
- Optional launch-forward feedback after shared reveal: 1–5 stars, up to three fixed tags, and a separately consented 300-character review that remains private to its author while linked.
- Single choice, multiple choice, free text, partner guessing, and weighted 1–5 prompts.
- Calendar-style timed or all-day countdowns with private reminder choices, upcoming/past views, one-way Android calendar export, encrypted offline edits, and partner change alerts.
- A preview-first Markdown workspace with live presence, cursor-stable synchronization, inline private images and GIFs, drafts, search, archives, and seven-day undo.
- Couple-authorized image, PDF, text, audio, and video attachments with resumable upload, malware scanning, metadata removal, verified private previews, optional offline copies, deletion, a 100 MiB file limit, and a 2 GiB couple quota.
- A content-free 30-day activity panel for note, attachment, countdown, quiz, and Smooch events, with a private seen position for each partner.
- Responsive Android navigation: a hamburger or left-edge swipe opens the drawer on phones, a bounded persistent rail stays visible on wide screens, and the right action panel appears only when the current screen has actions.
- Independent Home, Settings, and App updates destinations with a visible current-location state and guest-safe navigation filtering.
- Estimated nearby time from mutually consented, accuracy-aware chronological evidence. Direct intervals use five-minute evidence; a later strong anchor may confirm a missing span up to 20 minutes when no intervening evidence says apart or inaccurate. The detail screen animates seconds only through a five-minute server deadline; passive surfaces never extrapolate.
- Shared Markdown documents autosave after a short pause, retain encrypted crash/offline drafts, stop before overwriting a newer shared revision, and offer merge, fork-copy, or shared-version recovery. Clean private GIFs retain animation with pause/play and reduced-motion behavior.
- A dedicated Smooch tab using nine fixed emoji, a five-per-hour sender limit, orbit-pulse confirmation, per-device notifications, weekly totals, and retained history.
- Optional account-synced partner alerts for Smooches, the first document edit, countdown changes, daily quiz availability, partner completion, and shared results, with generic lock-screen text, independent delivery to each installation, authenticated first-party foreground hints, immediate opt-out cleanup, and self-hosted background polling. Android may delay background checks under Doze or manufacturer battery rules.
- Android home widget, Wear OS launcher, tile, and watch complication led by estimated nearby duration with honest fresh, stale, and unavailable states. The widget selects a compact layout when vertically resized. Relationship-scoped generations purge every surface on sign-out, unpair, or inactive pairing; a disconnected watch deletes its cache after 24 hours.
- Private cropped relationship avatars for the couple planets on the phone and Wear launcher. Each person chooses only their partner's picture; initials remain when a photo is absent.
- An in-app, phone-hosted wireless-debugging installer for the self-hosted Wear APK, with automatic or explicit manual endpoint selection, transient pairing codes, verified-download retry, and installed-version detection; no computer script or app store is required.
- In 1.1.0 source, a Watch settings child page selects one managed watch and controls photos, countdown titles, watch Smooches, update alerts, and the default destination. APK bytes are downloaded only after an explicit install, update, or repair action; private removal purges, uninstalls, forgets the local installer key, and guides wireless-debugging revocation.
- In 1.1.1 source, the first valid managed record binds that Wear relationship generation to one controller phone node. Other connected phones receive no watch payload or queue mutation authority. A side-by-side QA build embeds only the generated `.smoke` Wear APK and can never target the production package.
- An opt-in update detector that checks metadata every six hours and presents a once-per-launch update prompt; APK download and Android installation still require explicit approval and full verification.
- Eight-character, single-use pairing with confirmation.
- Relationship-scoped names and avatars chosen only by the other partner. Both people see the same friendly names across the phone, notifications, widget, and managed watch without changing either account identity.
- A public website for registration, account recovery, APK releases, privacy, and project documentation. Privileged administration is deliberately absent from the web app.
- Public patch notes at `/patch-notes` and a standards-based RSS feed at `/patch-notes.xml`.
- The separate Java/XML Big Orbit Android console with protected device-key enrollment, actionable global-question reports, service health, bounded account/session and registration controls, K-anonymous quiz intelligence, AI provenance, typed operations, backup evidence, and generic local alerts.
- Local weekly question intelligence through pinned Ollama generation and embedding models. Feedback learning receives only thresholded, sanitized product feedback; it never receives quiz answers or relationship data.
- In 1.3 source, Saturday 09:00 local learning and planning creates one seven-day arc with distinct daily themes; Sunday generation publishes three themed and two variety questions per day across an explicit light-to-deeper balance. Reviewed Markdown and allowlisted public context are bounded retrieval inputs, not model fine-tuning.
- A deterministic one-use reserve holds 1,825 general and 365 consent-centered intimacy prompts. Global generated content is checked for same-day, same-week, and preceding-365-day semantic repetition; custom couple questions remain private and exempt.
- Every fresh Big Orbit device begins with an eight-digit, ten-minute, hash-only PIN printed once by the server CLI, then proves its Android Keystore key. The first owner enrolls MFA from an in-app QR; existing MFA is never replaced by device enrollment.

![Implemented RC13 countdown timeline on a wide Android emulator](docs/assets/android-countdowns-rc13-tablet.png)

## Architecture

Android, Wear OS, [Big Orbit](https://github.com/Captainpax/big-orbit), and browsers connect to `https://lil-orb.pax-kun.com`. Nginx Proxy Manager forwards traffic to a single gateway port on the application host. The gateway routes `/api/*` and `/ws/*` to FastAPI and all other paths to Next.js. PostgreSQL, pgvector, Ollama, the worker, and Mailpit remain private to the Compose network. A secret-free context fetcher has a separate bounded egress network and accepts only code-owned HTTPS sources.

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

[`1.3.0`](https://github.com/Captainpax/littleorbit/releases/tag/v1.3.0) is the current signed stable release. The [phone APK](https://lil-orb.pax-kun.com/api/v1/releases/1.3.0/apk) is version code 29, 37,696,175 bytes, with SHA-256 `c5c879d458719e3ed27e5bdda38823d839600141ca08ff0d8967356df0d623e9`. The independently versioned [Wear APK](https://lil-orb.pax-kun.com/api/v1/releases/1.3.0/wear-apk) is version code 21, 14,737,944 bytes, with SHA-256 `0f0f0f221d80bbb5fc9db70773d8980b5b40136251df2fe4e64c8b3530e985cf`. Both artifacts use Android application ID `com.littleorbit.mobile` and retain the pinned [signing certificate](docs/signing/README.md). GitHub remains the canonical source history while identical APK bytes are served by Little Orbit's first-party API. Notifications are fully self-hosted; a visible app receives authenticated WebSocket hints and background WorkManager polls the same API, subject to Android battery delays. RC10.1 and RC11.1 require one manual update because their already-installed updater abandons its package session; automatic updates work after crossing that boundary.

The [1.3.0 release note](docs/releases/1.3.0.md) and [verification record](docs/operations/VERIFICATION-1.3.0-2026-09-23.md) record the exact artifacts, migration and backup evidence, public verification, and owner-deferred live-device observations.

The optional-update compatibility floor remains phone code 23. No forced-update deadline is scheduled.

## Privacy promise

Little Orbit collects only what a selected feature needs. AI question generation is site-wide and receives no answers, notes, profiles, locations, identifiers, or relationship history. In 1.2 it may receive K-anonymous ratings and separately consented, sanitized product reviews. Precise coordinates are kept for no more than 24 hours, administrator views exclude relationship content, and unpairing immediately stops sharing. Read the full [privacy design](docs/PRIVACY.md).

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
- [Latest stable verification record](docs/operations/VERIFICATION-1.3.0-2026-09-23.md)
- [1.3.0 release notes](docs/releases/1.3.0.md)

## License and support

The application code is licensed under the [MIT License](LICENSE). Optional donations may support hosting, but will never unlock features. Little Orbit hosts the primary signed phone APK; GitHub mirrors releases and remains the canonical source history.

Source, issues, and releases live at [github.com/Captainpax/littleorbit](https://github.com/Captainpax/littleorbit).
