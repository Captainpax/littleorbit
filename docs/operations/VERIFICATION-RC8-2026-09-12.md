# RC8 verification record — 2026-09-12

This record covers the RC8 home redesign, private profile images, phone-hosted Wear installation, release history, and patch-note feeds. It does not replace the open two-phone and physical-Wear launch gate.

## Automated checks

| Area | Command or check | Result |
|---|---|---|
| API style | `python -m ruff check services/api` in the API virtual environment | Passed |
| API types | `python -m mypy services/api` | Passed, 69 source files |
| API behavior | `python -m pytest services/api/tests` | Passed, 56 tests |
| Android domain/data/mobile/Wear | Unit suites plus phone and Wear `lintDebug` | Passed |
| Web style and types | `npm run lint` and `npm run typecheck` | Passed |
| Web behavior | `npm run test` | Passed, 20 tests in 3 files |
| Web production build | `npm run build` | Passed; `/patch-notes`, `/patch-notes.xml`, and `/app/install-wear` emitted |
| Signed Android release | `infra/scripts/build-signed-android.ps1` | Passed for phone and Wear; signer matched |
| API 36 emulator | Install signed RC8, cold launch, screenshot, and accessibility-tree dump | Passed; system bars did not overlap content |

The API image tests use generated solid-color fixtures. They verify metadata-free square WebP variants, upload media-type rejection, private ETag behavior, and authorization before partner-image lookup. Android policy tests cover non-watch rejection, downgrade rejection, current version, old/unknown patch warnings, and the May 1, 2026 boundary. Cross-language fixtures cover the authenticated profile response and public release history.

## Signed artifacts

- Phone version code 8: 23,277,980 bytes; SHA-256 `a20947a885959f0201f7559052b272fcd1a7d4f3f6057029d49521627270d156`.
- Wear version code 8: 14,130,618 bytes; SHA-256 `de1b1e5af6b983b412e89e46702396bd5db027a0a689697c5f28d577b5ef723c`.
- Certificate SHA-256: `43e83a420c7496ce9121339ab5bd6b01a6357161a83a95042ace56855bd89337`.
- Phone minimum API: 29. Wear minimum API: 30. Active compatibility floor remains phone version code 6, with no RC8 enforcement time.
- Two unchanged final signed builds produced the same phone and Wear hashes.

## Deployment verification

Pending final RC8 publication and live proxy checks. This section must record container health, migration `0011`, current/history metadata, complete and ranged phone/Wear downloads, patch-note HTML, RSS XML, Android App Links, and public HTTPS before the release is considered deployed.

## Open physical-device gate

The following checks were not claimed by automation:

- Crop, upload, removal, delete/re-add cache invalidation, unpair clearing, and photo synchronization on two physical phones and a watch.
- DNS-SD discovery, denied-permission manual fallback, first pairing, remembered reconnect, forgotten authorization, old-patch warning, and install/update on a physical Wear OS device.
- Full signup, pairing, quiz, note, countdown, location, widget, export, unpair, and archive flow on two real phones.
- OEM background-location and notification timing, battery use, large text, screen readers, and legal/privacy review.

RC8 remains a prerelease until those checks pass.
