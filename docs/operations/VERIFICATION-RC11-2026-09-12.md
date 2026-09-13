# RC11 verification — 2026-09-12

This record covers the RC11 Our Space, Markdown, attachment, Smooch, build, and deployment work. It records only checks completed against this source tree and the self-hosted stack.

## Automated gates

- `services/api/.venv/Scripts/python.exe -m pytest services/api/tests services/ai/tests`: 82 tests passed.
- `services/api/.venv/Scripts/python.exe -m ruff check services`: passed.
- `services/api/.venv/Scripts/python.exe -m mypy services`: 92 source files passed strict checking.
- `npm --prefix apps/web run check`: ESLint, strict TypeScript, 26 Vitest tests, and the 22-route production build passed.
- `gradlew` domain/data/widget/mobile/Wear unit tests plus phone and Wear release lint: 193 tasks completed successfully.
- `python infra/scripts/check_quality.py`: 265 source files passed the ratcheted size and complexity limits.
- `python infra/scripts/check_docs.py`, Markdownlint, and merged Compose validation passed after this record was added.

## Signed artifacts

- Phone: version `1.0.0-rc.11`, code 12, 35,543,921 bytes, SHA-256 `62bde4c1fc49470b15791602313e7fd65c7ee3d1022890cf39a246f4f3e7e2ce`.
- Wear: version `1.0.0-rc.11`, code 11, 14,133,462 bytes, SHA-256 `1860cd4bb30d31d3f9af5ef20aee639e8f5a8f416f3572e35936a53c45ef4a40`.
- Both APKs passed Android v3 signature verification, 16 KiB zip alignment, and certificate SHA-256 `43e83a420c7496ce9121339ab5bd6b01a6357161a83a95042ace56855bd89337`.
- Corrective RC11.1 phone code 13 is 35,543,945 bytes with SHA-256 `41eda9c366af6c8650197d490b56ba1d81a739de6cdc8b0c6dda123508de03d6`. Wear code 12 is 14,133,466 bytes with SHA-256 `04c91cbd20b0870656cd745a5880a53586a51ad8e83112fcb7aeff0b7a40f07a`; both retain the same signing certificate.
- Corrective RC11.2 phone code 14 is 35,543,945 bytes with SHA-256 `3faa50028016260de50fe59f8c5e7bfa381660df92d67e879d0634e6a410f44a`. Wear code 13 is 14,133,462 bytes with SHA-256 `3431664f1466f2241b3962c7da7d9b568bdaa04a0fd6213f14fda1c46c90d307`.
- Verification successor RC11.3 phone code 15 is 35,543,945 bytes with SHA-256 `d477e6ca3372b5d98d01249ad3ef16a626de51552199765236f1616aefb1e26a`. Wear code 14 is 14,133,466 bytes with SHA-256 `6d609669fd079ec179d9c39be01a3d9485392681a637c769b43cf5cdeab5641c`. Both retain the same signing certificate and pass v3 signature and 16 KiB alignment checks.

## Live stack and attachment pipeline

- PostgreSQL backup `little-orbit-20260912-214010.dump` was taken before migration.
- Compose built and started the API, web, worker, media worker, one-shot volume initializer, PostgreSQL, Ollama, and ClamAV. Migration `0013` is at head and both gateway health routes returned HTTP 200.
- Only gateway port 8180 is publicly bound by the base stack. Mailpit remains restricted to local development at `127.0.0.1:8025`.
- ClamAV 1.4.6 answered `PONG` using signature database 28115 dated September 6, 2026. Its attempted refresh could not resolve the upstream database host during this run; the mounted current database remained available and the scanner stayed healthy.
- A disposable live Markdown attachment moved from `pending_scan` to `available` through the real media worker, ClamAV stream scan, sanitizer, shared private volume, and PostgreSQL state. The test couple, accounts, note, row, staging bytes, and final bytes were removed afterward.
- The first live pipeline attempt exposed root-owned fresh-volume permissions and a missing model-registration import in the standalone worker. RC11 now uses a one-shot root initializer while every long-running application container remains UID/GID 65532, and the worker registers all persistence tables before claiming rows. The repeated live pipeline passed.
- An attachment-volume backup completed with an integrity manifest. The destructive attachment restore drill remains open.

## Android emulator

- A fresh API 36 Pixel 8 Pro emulator installed the signed phone APK and reported version code 12.
- Cold launch completed without a crash. The update-detection consent dialog was fully visible, and the five-tab Home, Quiz, Smooch, Space, and More navigation respected the status and gesture-navigation insets.
- A fresh RC10.1 emulator enabled automatic checks and discovered the published RC11 metadata. That real flow exposed an unreachable action button because the full Markdown release note exceeded the bottom-sheet height. RC11.1 bounds the summary and uses concise updater metadata.
- A repeated RC10.1 run downloaded and verified RC11.2, passed the unknown-source permission gate, and then recorded `committedMillis=0` with final status `Session was abandoned`. The installed RC10.1 code was still committing while its package-session stream was open; a downloaded release cannot replace that executing code before installation. RC10.1 and RC11.1 therefore require one manual update to cross this boundary.
- The signed RC11.2 build was installed and its application data cleared. It discovered published RC11.3, downloaded the 35,543,945-byte self-hosted APK, verified it, and opened Android's native update confirmation. Accepting the confirmation completed an in-place update to version code 15. Android recorded a nonzero commit time, `mCommitted=true`, `mPermissionsManuallyAccepted=true`, and final status `Session installed` for the application-owned session.
- RC11.3 then launched successfully with the five-tab inset-safe home screen and no newer update offer. This verifies automatic metadata discovery, first-party download, exact artifact verification, package-session commit, Android confirmation, and replacement after the one-time legacy boundary.

## Open physical gates

- The existing Pixel 8 Pro crossed the legacy boundary through an ADB in-place install from RC10.1 code 11 to RC11.3 code 15. Android reported installation success and the package identity changed to RC11.3; the locked screen prevented an honest physical UI-flow claim. Future releases can use the repaired updater on this phone.
- The complete two-real-phone shared editing, cursor/selection, conflict, every attachment preview type, Keep Offline, deletion, partner synchronization, Smooch notification, unpair archive, and reinstall flow remains open.
- The Wear installer and watch feature did not change in RC11, but the full phone-plus-watch release-gate rerun remains open.
- Battery, privacy/permission, backup-restore, DHCP reservation, and legal review gates in `ROADMAP.md` remain open. RC11 is a prerelease and is not the 1.0 general release.
