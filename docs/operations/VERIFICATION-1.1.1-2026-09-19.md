# 1.1.1 watch-hardening verification — 2026-09-19

This record separates completed QA from explicitly waived publication gates. Production 1.1.0 phone/Wear packages stayed installed during destructive smoke-package testing.

## Completed automated evidence

- Wear and phone debug unit suites passed.
- Wear and phone debug lint passed.
- Phone debug, phone smoke, Wear smoke, and Wear smoke-baseline APK assembly passed.
- Wear `connectedSmokeAndroidTest` passed on the physical Pixel Watch 3 with `-PwearTestBuildType=smoke`, including encrypted queue enqueue/decrypt and controller bind/purge behavior. The smoke-only test source prevents this destructive state exercise from targeting production.
- The watch log retained the original production code-19 `UnsupportedOperationException` at immutable queue insertion. After clearing that historical log, reinstalling/rerunning the code-20 smoke candidate, and exercising encrypted queue insertion, logcat contained zero Little Orbit fatal/ANR matches and zero token, authorization, pairing-code, latitude, or longitude patterns.
- Queue policy tests cover mutable insertion, five-item capacity, expiry, future-clock rejection, and operation-ID deduplication.
- Controller policy tests cover first-source binding, takeover rejection, newer purge handling, and safe rebind.
- The `verifyWearArtifactIsolation` build gate proves the ordinary debug phone APK has no embedded Wear APK and the smoke phone has its one fixed `assets/little-orbit-wear-smoke.apk`; direct ZIP inventory also found no smoke/QA-named debug entry.
- A smoke-only phone instrumentation verifier accepts the exact embedded Wear APK and rejects mutated byte count, hash, package, version, signer, and a truncated archive before watch contact.

## Completed device evidence

- The isolated stack started and fresh disposable accounts paired successfully. Account 0 ran on the physical Pixel 8 Pro; account 1 ran on the API 36 tablet emulator.
- Tablet Watch settings rendering was captured at 2560×1600. The responsive content width, managed-watch hero, and empty/no-watch state remained legible.
- Repeated Together Time diagnostic open/background/resume cycles on the tablet produced no fatal exception and no Room main-thread access error.
- The physical Pixel Watch 3 rendered the refreshed cosmic launcher and Smooch destination.
- The Wear QA package exercised missing/fresh install, code 19 baseline, upgrade to code 20, current-version repair, already-current inspection, removal, and restoration. `com.littleorbit.mobile` remained installed at Wear code 19 throughout; only `com.littleorbit.mobile.smoke` changed.
- Production and QA packages remained side by side on the physical phone and watch. The production phone was code 25 and the QA phone was code 26.

## Signed candidate evidence

- The protected signing pipeline built phone 1.1.1 code 26 and Wear 1.1.1 code 20 and emitted `dist/android/release-manifest.json`.
- Phone: 37,658,658 bytes; SHA-256 `a80a06513239b459522b3043083efc0cfce9e96e63cadbaadc5d0f3e3d3f1768`.
- Wear: 14,737,940 bytes; SHA-256 `b5f2af70402b6c8c5ff6feae91b5f23a32bd7c0ccea91b032ab705f8013d7f2b`.
- Both APKs verified under APK Signature Scheme v3 with exactly one signer and certificate SHA-256 `43e83a420c7496ce9121339ab5bd6b01a6357161a83a95042ace56855bd89337`.
- Independent `aapt` inspection found the expected production package and module-specific version code in each APK. Neither APK contains QA labels, `.smoke` identity, baseline identity, or the embedded smoke Wear APK.

## Not completed or not claimed

- The physical in-app Kadb wizard still needs current watch wireless-debug pairing endpoints and a short-lived pairing code for the full discovery/pair/transfer UI matrix.
- A second physical controller phone was not available for an observed cross-node rejection, though the pure policy and physical instrumentation paths passed.
- The complete fresh/stale/unavailable/unpaired/24-hour, tile, two-complication, and large-font screenshot matrix remains open.
- The exact signed candidate is local and verified, but manifest publication and production 1.1.0-to-1.1.1 phone/watch replacement are not claimed.
- The optional attachment smoke helper could not run because its Python `websockets` dependency was unavailable; it is unrelated to the watch patch and no attachment result is claimed.

## Explicitly waived publication gate

On 2026-09-19, the owner explicitly authorized publication without the remaining physical in-app wizard, second-controller-phone, complete passive-surface/large-font, and production in-place upgrade observations. Those items remain open and unperformed. The authorization changes the release decision only; it does not convert missing observations into passed evidence.

The verified signed candidate may therefore be published. If the immutable published build later requires correction, it must be replaced by new version codes and new bytes rather than overwritten.

## Production evidence

The immutable release row was published at `2026-09-19T23:45:53.67375Z` with phone code 26, Wear code 20, compatibility floor 23, and no `required_after` deadline. Local-gateway and public metadata matched the manifest, package identities, version codes, exact byte counts, SHA-256 values, signer, and GitHub release URL.

Complete local and public phone and Wear downloads independently matched the generated artifacts. Each local and public `bytes=0-1023` request returned 1,024 bytes with HTTP 206 and the correct total size. The local and public download page, patch-notes page, RSS feed, status page, showcase, and readiness endpoint returned HTTP 200; release-bearing pages and RSS exposed 1.1.1. Production containers were running and healthy where health checks apply, and release-service logs contained no traceback, unhandled, fatal, or error match during the rollout window.
