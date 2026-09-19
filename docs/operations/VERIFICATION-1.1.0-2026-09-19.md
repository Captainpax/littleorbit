# Little Orbit 1.1.0 verification — 2026-09-19

This living release-gate record covers the managed-watch update. It separates
automated source evidence, signed-artifact evidence, the explicitly waived
physical-device gate, and production evidence.

## Verified implementation

- Settings opens a dedicated Watch settings page with one explicit managed
  node, content choices, default destination, diagnostics, update/install,
  repair, and private removal.
- Active display, profile, and configuration records carry relationship and
  watch-target generations. A switch or removal advances the target barrier;
  old or non-target records cannot revive a purged cache.
- The installer has explicit install/update, repair, and removal modes. Opening
  it does not download APK bytes. Removal purges first, clears watch actions,
  uninstalls only Little Orbit, forgets the local key after success, and guides
  watch-side wireless-debugging revocation.
- Wear has vertical Together, Countdown, and Smooch destinations. Countdown
  retains timed/all-day and timezone fields. Smooch requires selection plus
  confirmation and stores at most five AES-GCM-protected requests for 15
  minutes.
- Watch actions contain no account credential. The phone requires the selected
  source node, protocol, current target and relationship generations, enabled
  preference, approved emoji, canonical identifier, and current creation
  window before its authenticated outbox accepts ownership.
- The tile remains passive and Nearby/Countdown are separate complications. No
  passive surface sends a Smooch.

## Automated checks

| Check | Result |
| --- | --- |
| Domain tests, including watch message policy | Passed |
| Android data tests, including managed-destination policy | Passed |
| Android mobile unit tests | Passed |
| Wear unit tests, including cache expiry and stale behavior | Passed |
| Android mobile and Wear debug lint | Passed |
| Java/XML debug compilation and phone/Wear assembly | Passed |
| Debug APK manifest analysis | Passed: package `com.littleorbit.mobile`; phone `1.1.0` code 25; Wear `1.1.0` code 19 |
| Repository size and complexity limits | Passed, 440 source files |
| Documentation inventory and Markdown lint | Passed before release-record edits and repeated before tagging |
| `git diff --check` | Passed before release-record edits and repeated before tagging |

The first matrix run exposed an API-30-incompatible
`Duration.toMinutesPart()` call and old cache-test constructor use. Both were
corrected before the complete unit/lint/build matrix passed.

## Signed artifacts

- Phone `1.1.0` code 25: 37,636,082 bytes; SHA-256
  `9b205633c004d4681413cc10592bb1ebc628dde8f3822754387552b2a09b101f`.
- Wear `1.1.0` code 19: 14,730,416 bytes; SHA-256
  `357b176ba4d6d07b7eae40601aa8595806a1c0aad32b6a1dcbed41271e000950`.
- Both APKs passed Android signature-scheme v3 verification and independently
  report certificate SHA-256
  `43e83a420c7496ce9121339ab5bd6b01a6357161a83a95042ace56855bd89337`.
- Independent manifest inspection reports phone minimum API 29 and Wear minimum
  API 30. The publication compatibility floor remains phone code 23 with no
  forced-update deadline.

## Explicitly waived device gate

A physical Pixel 8 Pro was connected, but the debug APK was not installed over
the production-signed app because that signature mismatch would require an
uninstall and local-data loss. No Wear device was connected. First install,
remembered update, repair, private removal, target switch, offline Smooch
acceptance/expiry, preference revocation, 24-hour deletion, large text, tile,
and both complications therefore remain untested on physical watch hardware.

The owner explicitly approved shipping on 2026-09-19 with this unavailable
physical Wear-device gate waived. This approval does not convert the missing
checks into evidence; they remain open follow-up work.

## Production evidence

Publication, production deployment, API/web health, complete and byte-range
download verification, public hash comparison, patch notes, and RSS checks are
pending and must be appended after successful rollout.
