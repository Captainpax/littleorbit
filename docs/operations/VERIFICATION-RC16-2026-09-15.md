# RC16 verification — 2026-09-15

## Scope and diagnosis

This record covers the Android stale-session correction prompted by a screen that simultaneously showed cached couple avatars, a local signed-in state, and “Not connected.” A privacy-limited production metadata query confirmed that the reported relationship has one active, non-ended couple with exactly two active verified members. No couple or membership row was edited. The affected partner account had no active server session, which explains both the pairing presentation and inability to load shared notes; the note records remained attached to the active couple.

The root cause was split local cleanup. Display refresh already removed the relationship summary after HTTP 401, but the encrypted session marker and cached profile thumbnails survived. Home therefore mapped the phone to a signed-in account without a relationship cache, while profile rendering supplied stale avatars.

## Corrected invariants

- HTTP 401 from authenticated repositories and profile/display refreshes clears the complete local account context.
- Public login and password-confirmation failures do not use that automatic purge because their 401 response does not establish bearer-session loss.
- The exact structured `relationship_inactive` 409 remains a relationship-only purge and preserves the valid account session.
- Home maps failed refreshes using the post-request session state, so an asynchronous callback cannot resurrect the stale signed-in fallback.
- A late profile callback cannot render pair thumbnails after the session has been removed.
- Home derives completion from current readiness and removes the setup checklist after all four core steps pass; revoked readiness makes it visible again.
- Pairing controls remain hidden until the server distinguishes an active relationship from an unpaired account. Only the connected state exposes the confirmed, archive-preserving unpair action.

## Automated and device evidence

- Android data and mobile unit tests passed, including wrapped-401 classification, account-purge invocation, relationship-only separation, invalid-session Home recovery, and preservation of an authorized offline cache.
- The focused setup-state regression passed after adding automatic completed-state hiding, and the signed release build plus release lint gate passed with the connected relationship/unpair layout.
- Android phone debug lint passed.
- A fresh disposable couple on the isolated smoke stack signed in on an API 36 phone emulator, opened Our Space, discovered the partner-visible document, downloaded both sanitized inline attachments, and rendered their verified previews.
- The test then revoked only that disposable account's server sessions and cold-launched the app. Home rendered “Welcome to your orbit” and “Sign in to sync,” with no cached photos or false pairing action. Direct app-private checks found no encrypted session entry or profile thumbnail/name entry, and logcat contained no Little Orbit fatal event.
- The authorized physical Pixel upgraded in place to signed phone code 21 without clearing app data. Its valid session remained active, completed setup stayed absent from Home, and Pairing & relationship showed **Unpair from partner** while hiding pair-code creation. The real relationship was not unpaired; the archive-and-purge mutation remains part of the disposable two-phone gate.
- The isolated Compose project was stopped with `--volumes`; its database, accounts, Mailpit messages, attachment bytes, and generated service volumes were removed.

![RC16 signed-out recovery after disposable session revocation](../assets/android-session-expired-rc16-emulator.png)

## Signed artifact evidence

| Artifact | Version code | Bytes | SHA-256 |
| --- | ---: | ---: | --- |
| Phone `1.0.0-rc.16` | 21 | 36,220,661 | `695982dd44ea99a9174af0d84ff24fcb696b841552216599f281d228135b3872` |
| Wear `1.0.0-rc.14` reused | 16 | 14,188,854 | `6ce385654e323dfdcad9d5b6dec000a4f2549568d30b604ce6ea1400d642f0b6` |

Both artifacts verify with certificate SHA-256 `43e83a420c7496ce9121339ab5bd6b01a6357161a83a95042ace56855bd89337`. Wear behavior did not change; its bytes are identical to the RC14 and RC15 companion.

## Publication evidence

- Git tag and GitHub prerelease `v1.0.0-rc.16` point to tested commit `9901735` and expose the two APKs, two checksum sidecars, and generated manifest. GitHub reports the exact APK byte counts and digests above.
- The self-hosted API published the immutable RC16 record at `2026-09-15T05:34:32.418302Z` with phone code 21, Wear code 16, compatibility floor 6, and no enforcement instant.
- Complete public downloads produced 36,220,661 phone bytes and 14,188,854 Wear bytes with the exact signed SHA-256 values. A phone request for bytes 0–1023 returned `206`, the exact `Content-Range` total, and 1,024 bytes.
- Public `/download`, `/patch-notes`, and `/patch-notes.xml` returned `200`, named RC16, and served the RSS endpoint as `application/rss+xml`.
- Local and public readiness returned `200`; all eight long-running Compose services were running, every service with a configured health check was healthy, and recent API/web/gateway logs contained no fatal, panic, uncaught, or traceback match.

## Open release gates

The affected partner must install RC16 and sign in again because a client cannot recover the raw value of a revoked server token. A two-physical-phone follow-up must confirm that the existing couple, shared-note directory, notifications, and avatars return after that sign-in. The remaining 1.0 gates in the roadmap are unchanged.
