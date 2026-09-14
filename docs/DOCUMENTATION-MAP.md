# Documentation map

This inventory assigns every repository-owned Markdown file to a purpose. Review the full list for every change, update every affected file, create a missing document when the behavior has no honest home, and always review `ROADMAP.md`. `python infra/scripts/check_docs.py` fails when a Markdown file is missing from this inventory or a listed file no longer exists.

## Project, community, and policy

<!-- documentation-inventory:start -->
- `AGENTS.md` — repository mission, invariants, quality rules, and cross-system commands.
- `CODE_OF_CONDUCT.md` — community behavior and enforcement expectations.
- `CONTRIBUTING.md` — contributor setup, code standards, documentation workflow, and review gates.
- `CONTRIBUTORS.md` — contributor routes and project credits.
- `README.md` — public mission, feature summary, current release, quick start, and document index.
- `ROADMAP.md` — completed 1.0 scope and future 1.x/2.0 direction; always review.
- `SECURITY.md` — supported versions, private reporting, and security boundaries.
- `SHOWCASE.md` — concept art, current visual evidence, and screenshot checklist.
- `THIRD_PARTY_NOTICES.md` — directly used third-party components and license notices.

## Major-system agent guides

- `apps/android/AGENTS.md` — phone, widget, and Wear implementation rules.
- `apps/web/AGENTS.md` — public site and owner-console implementation rules.
- `docs/AGENTS.md` — documentation, Mermaid, screenshot, and verification rules.
- `infra/AGENTS.md` — container, gateway, firewall, backup, GPU, and secret rules.
- `services/ai/AGENTS.md` — model privacy, schema, validation, fallback, and evaluation rules.
- `services/api/AGENTS.md` — API authorization, transaction, migration, and WSS rules.

## Architecture, privacy, and protocol

- `docs/DOCUMENTATION-MAP.md` — this complete Markdown inventory and ownership map.
- `docs/NETWORK-FLOW.md` — editable Mermaid source of truth for network and logic flows.
- `docs/PRIVACY.md` — data, purpose, access, retention, consent, AI, location, and update boundaries.
- `protocol/README.md` — versioned cross-language contract and fixture conventions.

## Architecture decisions

- `docs/adr/0001-monorepo-modular-monolith.md` — repository and service architecture.
- `docs/adr/0002-owned-authentication.md` — owned email/password authentication.
- `docs/adr/0003-private-local-ai.md` — private local global-question generation.
- `docs/adr/0004-android-java-modules.md` — Java/XML Android module boundaries.
- `docs/adr/0005-server-authoritative-notes.md` — revisioned shared-note synchronization.
- `docs/adr/0006-account-erasure-reference-policy.md` — account deletion references.
- `docs/adr/0007-encrypted-android-offline-queues.md` — encrypted retryable Android work.
- `docs/adr/0008-separated-session-lifetimes.md` — app and admin session separation.
- `docs/adr/0009-verified-sideload-updates.md` — verified user-driven phone updates.
- `docs/adr/0010-first-party-apk-delivery.md` — resumable self-hosted APK delivery.
- `docs/adr/0011-stable-daily-quiz-snapshots.md` — stable quiz sets and reveal behavior.
- `docs/adr/0012-relationship-age-proximity-and-wear-delivery.md` — relationship date, proximity, and original Wear delivery.
- `docs/adr/0013-private-profile-images.md` — normalized owner/current-partner profile images.
- `docs/adr/0014-phone-hosted-wear-installation.md` — in-app local wireless-ADB installation.
- `docs/adr/0015-pair-instant-and-continuous-proximity.md` — pairing-based age and visible continuous proximity collection.
- `docs/adr/0016-durable-smooches.md` — bounded private signals, weekly history, archive, and deletion rules.
- `docs/adr/0017-note-workspace-lifecycle.md` — multiple titled notes, presence, metadata operations, and archive recovery.
- `docs/adr/0018-opt-in-update-discovery.md` — scheduled metadata discovery while APK transfer remains user-driven.
- `docs/adr/0019-wear-adb-transport-compatibility.md` — Android 17 discovery, public TLS, lazy ADB connection proof, and package-session installation.
- `docs/adr/0020-markdown-space-and-private-attachments.md` — safe Markdown rendering and scanned private attachment storage.
- `docs/adr/0021-responsive-shell-and-private-activity.md` — responsive Android navigation, contextual panels, and the content-free 30-day couple timeline.
- `docs/adr/0022-self-hosted-per-device-notifications.md` — account choices, random installations, content-free hints, and independent delivery acknowledgement.
- `docs/adr/0023-partner-assigned-relationship-avatars.md` — relationship-scoped images selected only by the other partner.
- `docs/adr/0024-calendar-countdowns-and-transition-alerts.md` — timed/all-day moments, private reminders, one-way calendar export, and countdown/quiz alerts.

## Operations and verification

- `docs/operations/BACKUP-RESTORE.md` — PostgreSQL and immutable release recovery.
- `docs/operations/DEPLOYMENT.md` — production Compose, NPM, firewall, and release runbook.
- `docs/operations/LOCAL-DEVELOPMENT.md` — local stack, updater, Wear installer, and photo development.
- `docs/operations/WEAR-INSTALLER.md` — user flow and physical-device verification checklist.
- `docs/operations/VERIFICATION-2026-09-11.md` — initial system verification evidence.
- `docs/operations/VERIFICATION-2026-09-12.md` — follow-up system verification evidence.
- `docs/operations/VERIFICATION-RC5-2026-09-12.md` — RC5 quiz and AI verification evidence.
- `docs/operations/VERIFICATION-RC6-2026-09-12.md` — RC6 relationship/location/Wear verification evidence.
- `docs/operations/VERIFICATION-RC7-2026-09-12.md` — RC7 round-Wear correction evidence.
- `docs/operations/VERIFICATION-RC8-2026-09-12.md` — RC8 profile, installer, patch-note, build, and deployment evidence.
- `docs/operations/VERIFICATION-RC9-2026-09-12.md` — RC9 widget, quiz exit, crop, physical-Pixel, build, and deployment evidence.
- `docs/operations/VERIFICATION-RC10-2026-09-12.md` — RC10 pair age, proximity, Smooch, notes, updater, Wear, build, deployment, and device evidence.
- `docs/operations/VERIFICATION-RC10.1-2026-09-12.md` — RC10.1 physical wireless-pairing, remembered reconnect, package-session, and signed-artifact evidence.
- `docs/operations/VERIFICATION-RC11-2026-09-12.md` — RC11 Markdown, attachment, UI, build, deployment, and device evidence.
- `docs/operations/VERIFICATION-RC12-2026-09-13.md` — RC12 shell, activity, attachment, compatibility-matrix, build, and release evidence.
- `docs/operations/VERIFICATION-RC12.1-2026-09-13.md` — RC12.1 preview, notification, compatibility, artifact, and deployment evidence.
- `docs/operations/VERIFICATION-RC13-2026-09-13.md` — RC13 countdown, quiz, AI whitespace, avatar, compatibility, artifact, and deployment evidence.
- `docs/signing/README.md` — public certificate identity and private-key handling.

## Immutable release notes

- `docs/releases/1.0.0-rc.1.md` — RC1 signed baseline.
- `docs/releases/1.0.0-rc.2.md` — RC2 session and cleanup fixes.
- `docs/releases/1.0.0-rc.3.md` — RC3 updater and cosmic interface.
- `docs/releases/1.0.0-rc.4.md` — RC4 first-party downloads.
- `docs/releases/1.0.0-rc.5.md` — RC5 daily quiz and AI pipeline.
- `docs/releases/1.0.0-rc.6.md` — RC6 insets, relationship age, proximity, permissions, and Wear.
- `docs/releases/1.0.0-rc.7.md` — RC7 round-display correction.
- `docs/releases/1.0.0-rc.8.md` — RC8 home, photos, in-app Wear install, and patch notes.
- `docs/releases/1.0.0-rc.9.md` — RC9 widget crash, quiz completion, and profile-crop corrections.
- `docs/releases/1.0.0-rc.10.md` — RC10 pair age, continuous proximity, Smooches, notes workspace, update discovery, and Wear recovery.
- `docs/releases/1.0.0-rc.10.1.md` — RC10.1 Wear artifact and phone-hosted installer correction.
- `docs/releases/1.0.0-rc.11.md` — RC11 Our Space, cursor-stable Markdown, attachments, and dedicated Smooch tab.
- `docs/releases/1.0.0-rc.11.1.md` — corrective RC11 updater action visibility and concise in-app notes.
- `docs/releases/1.0.0-rc.11.2.md` — corrective Android package-session stream ordering.
- `docs/releases/1.0.0-rc.11.3.md` — repaired updater path verification candidate and legacy boundary.
- `docs/releases/1.0.0-rc.12.md` — responsive shell, private activity, Markdown dock, attachment repair, and isolated smoke workflow.
- `docs/releases/1.0.0-rc.12.1.md` — preview-first documents, inline private images, per-device notifications, motion, and Android 10 repairs.
- `docs/releases/1.0.0-rc.13.md` — calendar-style countdowns, quiz transitions, generated-text validation, and partner-assigned avatars.
<!-- documentation-inventory:end -->

## Review routing

Changes to public behavior normally affect README, SHOWCASE, ROADMAP, one release note, and a verification record. Data or permissions affect PRIVACY and SECURITY. Trust, transport, authorization, synchronization, or background work affects NETWORK-FLOW and usually an ADR. Deployment, secrets, migrations, backups, APK publication, or device setup affects an operations guide. Contract changes affect `protocol/README.md` and versioned fixtures even when their payload details stay out of prose.

Historical release and verification records are immutable evidence. Correct a past factual error with a clearly scoped correction or new record; never rewrite a prior test as though it covered later behavior.
