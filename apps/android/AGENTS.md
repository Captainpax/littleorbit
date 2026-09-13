# Android agent guide

## Role

Own the Java phone app, shared domain/data libraries, home widget, Wear OS tile, and watch complication.

## Boundaries

- `domain`: platform-free immutable models and pure calculations.
- `data`: DTOs, Room entities, repositories, Retrofit, WorkManager, and mapping.
- `mobile`: activities/fragments, XML, screen state, navigation, permissions, and widget.
- `wear`: Wear OS UI, tile, complication, and cache synchronization.

## Hard rules and invariants

- Production source is Java 17 and XML Views. Do not add Kotlin production code or Compose.
- Activities/fragments render immutable state and forward actions. Repositories own I/O; meaningful cross-repository workflows belong in use cases.
- Store access tokens only in encrypted app storage and never expose them to widgets, complications, logs, intents, or backups.
- Location collection requires explicit consent and current permission. The foreground service stays visible, WorkManager remains a bounded recovery path, and both may collect offline. Queue encrypted samples; stop immediately and clear the queue after permission or sharing is revoked.
- Widgets and wear surfaces read a minimal cache containing together-time, next countdown, update instant, and no relationship content.
- Every cached surface shows when data is stale or unavailable.
- Offline changes need stable operation IDs. Preserve note drafts when the server revision diverges. Bind asynchronous note results to the note ID that initiated them.
- Keep one WSS session per open note, preserve UTF-16 cursor/selection while applying code-point server edits, render Markdown without raw HTML or automatic remote images, and verify sanitized attachment hashes before preview or app-private offline retention.
- Our Space renders CommonMark/GFM without raw HTML or automatic remote images. Preserve cursor and selection when acknowledgements arrive. Attachment previews must verify sanitized hashes, stay app-private, and remove stale offline copies after deletion, unpairing, or account changes.
- Top-level destinations live in the left navigation drawer. At 840dp and wider it becomes a static, non-modal rail; it must never consume touches aimed at screen content. The right drawer contains actions for the current destination and cannot open from the system-back edge.
- Queue at most five encrypted Smooch sends for at most 15 minutes. Never manufacture delivery after expiration, and keep lock-screen content private by default.
- Release APKs require all four `ANDROID_SIGNING_*` values, use the same protected key for phone and Wear OS, and must pass `apksigner verify` before publication. Never commit or replace the private release key.
- Build against Android SDK 37 with Java 17 source. Keep target SDK 36 until the Android 17 local-network permission migration is designed and tested.
- Wireless-ADB pairing uses public Conscrypt APIs and authenticated commands. Never add hidden-API access, log pairing material, trust a pre-command Kadb connection flag, or publish values copied from the wrong module's output metadata.
- Increase `versionCode` for every published update. A reused code or different certificate prevents safe upgrades.
- Fetch release metadata only from the public API. Accept APK links only from the exact versioned `lil-orb.pax-kun.com` API endpoint or the historical canonical GitHub repository, then verify byte count, SHA-256, package name, increasing version code, and the pinned certificate before opening Android's installer.
- Keep updater progress restart-safe and detect a running or paused transfer with no progress for five minutes. Background work may fetch metadata but must never download or install an APK without a user action. Required updates begin only after the server's explicit UTC enforcement time.
- Inventory every repository-owned Markdown file for each Android update. Update or create all affected public, operations, architecture, release, and contributor documents, and always review and update `ROADMAP.md` for behavior, scope, milestone, or release changes.

## Start here

- Root rules: [`../../AGENTS.md`](../../AGENTS.md)
- Contracts: [`../../protocol/`](../../protocol/)
- Privacy: [`../../docs/PRIVACY.md`](../../docs/PRIVACY.md)
- Android decisions: [`../../docs/adr/0004-android-java-modules.md`](../../docs/adr/0004-android-java-modules.md)

## Commands and required tests

```bash
./gradlew :apps:android:domain:test :apps:android:data:testDebugUnitTest
./gradlew :apps:android:mobile:testDebugUnitTest :apps:android:mobile:lintDebug
./gradlew :apps:android:wear:testDebugUnitTest :apps:android:wear:lintDebug
./gradlew :apps:android:mobile:connectedDebugAndroidTest
.\infra\scripts\build-signed-android.ps1
.\infra\scripts\android-smoke.ps1 -Serial <emulator-serial> -AccountIndex 0 -ResetApp
```

Test DTO/domain separation, Room migrations, retries and duplicate work, stale cache rendering, permission removal, clock/timezone boundaries, updater corruption and restart recovery, process death, reboot, unauthorized responses, widget updates, and Wear disconnection.
Run the isolated paired-account smoke flow on the supported API floor, an intermediate API, the current target API, and a wide tablet. Launch the Wear APK on a watch emulator and preserve screenshots under ignored verification output.

## Documentation impact

Update SHOWCASE for visible behavior, PRIVACY for permissions/data, NETWORK-FLOW for transport, and an ADR for module or storage changes.

## Common mistakes

- Putting Android types in domain models.
- Sharing Room entities or Retrofit DTOs with UI code.
- Assuming the phone, widget, and watch refresh together.
- Scheduling unbounded work or exact alarms without a product requirement.
- Treating a location permission grant as consent to share.
- Trusting only a metadata checksum without independently pinning the expected Android signing certificate.
