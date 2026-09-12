# RC7 verification record — 2026-09-12

RC7 is a narrow immutable follow-up to the published RC6 binaries. A round Wear OS 5 emulator exposed clipped fallback content, so the correction uses version code 7 rather than replacing RC6.

## Release identity

- Phone APK: 15,907,214 bytes, SHA-256 `426618ec1051d54c9c391ccb5850b78b11f25f49cb8a4daf2394c0e7db79a35e`.
- Wear APK: 14,124,818 bytes, SHA-256 `615d18689b76b19e303a0423bce553c08e8ce77f0042c9b28d4ede4bf81d50a1`.
- Both packages use version code 7, version name `1.0.0-rc.7`, package `com.littleorbit.mobile`, and signing-certificate SHA-256 `43e83a420c7496ce9121339ab5bd6b01a6357161a83a95042ace56855bd89337`.
- The RC6 minimum phone version code 6 remains active. RC7 does not raise it.

## Verified behavior

- Wear unit tests and lint passed after the layout change.
- Two consecutive release builds produced identical phone and Wear hashes.
- The signed Wear APK installed on a new round Wear OS 5/API 34 x86_64 emulator and cold-launched `WearActivity`.
- The fallback logo, relationship text, nearby estimate, and stale state fit the round safe area; a scroll container protects larger text and smaller screens.
- The signed phone package remains API 29+, and the Wear package remains API 30+ with the watch hardware feature.

## Public deployment

Pending immutable tag, GitHub mirror, first-party phone/Wear publication, complete/range/hash checks, and responsive download-page verification.

## Remaining release gates

The two-phone and physical-Wear flow, tile and complication selection, real notification/location behavior, battery measurements, and accessibility testing remain. RC7 is a prerelease.
