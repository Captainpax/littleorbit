# RC7 verification record — 2026-09-12

RC7 is a narrow immutable follow-up to the published RC6 binaries. A round Wear OS 5 emulator exposed clipped fallback content, so the correction uses version code 7 rather than replacing RC6.

## Release identity

- Release source commit: `058ce0883ba43601a8eb077362a102670810b018`, preserved by immutable tag `v1.0.0-rc.7`.
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

- GitHub prerelease `v1.0.0-rc.7` contains both exact APKs and checksum sidecars.
- The API published complete phone and Wear metadata at `2026-09-12T17:50:53.316099Z`. RC7 has no required time and retains minimum supported version code 6.
- Public HEAD requests returned the exact sizes, immutable caching, checksum headers, and byte-range support. `0-1023` requests returned `206` and correct complete sizes.
- Complete first-party phone and Wear downloads matched their signed build byte counts and SHA-256 values.
- The live download page returned `200` with RC7, both hashes, and Wear content. All 12 public desktop/mobile Playwright flows passed against production.
- Version code 5 remained blocked with `426`; version codes 6 and 7 reached authentication with `401`.
- API, web, gateway, PostgreSQL, and Ollama were healthy after publication; the worker remained running. Gateway context-cancelled warnings came from Playwright abandoning speculative Next.js prefetches during navigation, with no failed page requests or browser errors.

## Remaining release gates

The two-phone and physical-Wear flow, tile and complication selection, real notification/location behavior, battery measurements, and accessibility testing remain. RC7 is a prerelease.
