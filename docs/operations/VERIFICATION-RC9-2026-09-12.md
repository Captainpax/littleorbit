# RC9 verification record — 2026-09-12

This record covers the RC9 widget lifecycle correction, quiz reveal exit, and profile crop flow. It does not replace the open two-phone and physical-Wear launch gate.

## Root-cause evidence

Android DropBox on the physical phone recorded RC8 crashes at 13:35, 13:45, and 14:08 local time. Each was `Package: com.littleorbit.mobile v8 (1.0.0-rc.8)` with a null `BroadcastReceiver.PendingResult.finish()` call from `LittleOrbitWidgetProvider`. The old code manually constructed a receiver and then called a path that used `goAsync()`, so Android had not attached the pending result the background thread attempted to finish.

The crop dependency exposed its approval action through its activity menu. Little Orbit uses a no-action-bar theme, leaving the third-party crop content visible without its approval control. RC9 removes that activity from the merged manifest and embeds the crop view in a first-party inset-aware activity with fixed controls.

## Automated checks

| Area | Command or check | Result |
|---|---|---|
| API and AI behavior | `python -m pytest -q services/api/tests services/ai/tests` | Passed, 64 tests |
| Python style and types | Ruff plus strict mypy over `services` | Passed, 77 typed source files |
| Android domain/data/widget/mobile/Wear | Unit suites plus phone and Wear `lintDebug` | Passed |
| API 36 instrumentation | `:apps:android:mobile:connectedDebugAndroidTest` | Passed, 3 tests |
| Manifest boundary | Inspect merged release manifest | Passed; internal crop activity is not exported and the library activity is absent |
| Web style, types, behavior, and build | `npm --prefix apps/web run check` | Passed, 20 tests and 22 generated routes |
| Web browser flows | `npm --prefix apps/web run test:e2e` | Passed, 16 desktop/mobile tests |
| Repository limits and docs | Quality ratchet, documentation inventory, links, and Markdown lint | Passed; 225 source files and 57 Markdown files checked |
| Signed Android release | `infra/scripts/build-signed-android.ps1` twice without source changes | Passed for phone and Wear; hashes and signer matched |

Widget unit tests cover unavailable start dates, future-date clamping, and the exact stale threshold. Quiz state tests cover loading, question, review, waiting, and revealed priority. The instrumentation smoke test opens the internal crop screen and verifies the visible **Cancel** and **Use photo** controls.

## Physical Pixel 8 Pro

The signed RC9 phone APK upgraded RC8 in place and retained account state on a Pixel 8 Pro running Android 17/API 37 with the 2026-08-05 security patch. The complete crop interaction ran on the signed RC9 candidate immediately before the final control-state guard; the final delta only keeps Cancel enabled while loading and disables approval after load failure, and passed the emulator suite. Pulling the installed base APK after the final install produced the exact published 23,285,988-byte file and SHA-256. Package inspection reported version code 9 and `1.0.0-rc.9`.

- Opened an already revealed five-question quiz and confirmed the completed progress state plus fixed **Done** action.
- Tapped **Done**, returned to `MainActivity`, and confirmed the app process remained alive.
- Selected a generated synthetic image, reached the first-party crop flow, approved it, and received the successful profile-update state.
- Removed the synthetic profile through the app, confirmed the initial fallback and disabled removal action, then deleted the exact local test fixture.
- Sent the widget refresh broadcast to the exact final APK while the phone was locked; the broadcast and WorkManager render completed without a filtered widget error.
- Checked filtered Android runtime, widget, and crop logs after the RC9 flow; no new error was present.
- Checked Android DropBox; the newest Little Orbit crash remained the earlier RC8 version-code-8 record.

The synthetic test image contained no real person, was removed from the account and phone, and is not part of the repository.

## Signed artifacts

- Phone version code 9: 23,285,988 bytes; SHA-256 `28cdcbc6cd58b26507979e77562de6123e15628766b605108e1c98c26da016b3`.
- Wear version code 9: 14,130,618 bytes; SHA-256 `e51241347840273667956e60dc36c560ef2e9b4dab2b57f7f89374dfae4c4036`.
- Certificate SHA-256: `43e83a420c7496ce9121339ab5bd6b01a6357161a83a95042ace56855bd89337`.
- Phone minimum API: 29. Wear minimum API: 30. Active compatibility floor remains phone version code 6, with no RC9 enforcement time.
- Two unchanged final signed builds produced the same phone and Wear hashes.

## Deployment verification

- Pushed commit `5de32c1` and annotated tag `v1.0.0-rc.9`, then created the GitHub prerelease with the exact phone/Wear APKs and checksum sidecars. GitHub reported the expected 23,285,988-byte and 14,130,618-byte assets.
- Copied the same verified bytes into ignored release storage, rebuilt the production web image, and confirmed API, web, gateway, PostgreSQL, and Ollama health. Only gateway port 8180 was host-bound.
- Published one immutable release record at `2026-09-12T21:52:55.481551Z`. The public current response and release history returned RC9 first with code 9, exact hashes and sizes, minimum phone API 29, compatibility floor 6, and no enforcement time.
- Downloaded both complete APKs through public HTTPS and reproduced the local sizes and SHA-256 hashes.
- Requested bytes 1,048,576 through 1,049,599 for each APK through Nginx Proxy Manager. Both returned `206`, exactly 1,024 bytes, the correct full-file `Content-Range`, immutable cache control, ETag, byte-range support, and `X-Checksum-SHA256`.
- Confirmed `/patch-notes` presents RC9 and `/patch-notes.xml` parses as RSS 2.0 with RC9 first.
- Confirmed `/download` presents RC9 and its exact phone SHA-256 after the rebuilt web container became healthy.
- Confirmed `/.well-known/assetlinks.json` still binds `com.littleorbit.mobile` to the pinned signing certificate.

Public checks used `https://lil-orb.pax-kun.com` through Nginx Proxy Manager and the gateway rather than direct container ports.

## Open release gate

- Complete profile partner/watch synchronization on physical devices.
- Run the full signup, pairing, quiz, note, countdown, location, widget, export, unpair, and archive flow on two real phones.
- Install and update the companion on a physical Wear OS watch, then verify the launcher, tile, complication, stale state, and disconnect recovery.
- Complete OEM background-location, notification timing, battery, large-text, screen-reader, DHCP-reservation, and legal/privacy checks.

RC9 remains a prerelease until those checks pass.
