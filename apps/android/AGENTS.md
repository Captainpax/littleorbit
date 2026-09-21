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
- Treat HTTP 401 from an authenticated repository or profile/display refresh as terminal session loss: clear the token and all account/relationship state, stop private work, and render signed out. Do not apply that policy to public sign-in or a wrong-password deletion proof. Keep the exact `relationship_inactive` 409 as a relationship-only purge that preserves the account session.
- Location collection requires explicit consent and current permission. The foreground service stays visible and samples about every two minutes; WorkManager remains an inexact 15-minute recovery path, and both may collect offline. Queue encrypted samples with the exact relationship ID and generation; stop immediately and clear the queue after permission or sharing is revoked. Temporary network, server, or throttle failures retain the bounded queue.
- Widgets and Wear surfaces read a minimal cache containing authoritative observed nearby time, next countdown, update instant, opaque relationship identity, and no relationship content. Passive surfaces never extrapolate a live proximity lease.
- Scope every passive payload to a monotonic relationship generation. Sign-out, unpair, and `relationship_inactive` publish an urgent durable purge before clearing phone state; the watch applies purge markers before data, rejects older generations, and rechecks asynchronous assets before committing them.
- Every cached surface shows when data is stale or unavailable. A disconnected watch deletes display values, names, thumbnails, and pending thumbnail files after 24 hours; every read enforces the deadline even if its best-effort alarm did not run.
- Offline changes need stable operation IDs. Preserve note drafts when the server revision diverges. Bind asynchronous note results to the note ID that initiated them.
- Keep one foreground WSS session per open note, close it when the editor loses foreground focus, and fetch a fresh authorized snapshot before reconnecting. Preserve UTF-16 cursor/selection while applying code-point server edits, render Markdown without raw HTML or automatic remote images, and verify sanitized attachment hashes before preview or app-private offline retention.
- Our Space renders CommonMark/GFM without raw HTML or automatic remote images. Preserve cursor and selection when acknowledgements arrive. Attachment previews must verify sanitized hashes, stay app-private, and remove stale offline copies after deletion, unpairing, or account changes.
- Top-level destinations live in the left navigation drawer; Home, Settings, and App updates remain independent activities with one visible selected state. Phones expose both a hamburger and a narrow left-edge swipe region. At 840dp and wider navigation becomes a bounded static, non-modal rail and content stays width-bounded; neither may consume touches aimed at the other. Hide the right drawer affordance when a destination has no actions, and never let that drawer open from the system-back edge.
- Derive Home setup readiness from current pairing, permission, consent, widget, and watch state. Hide the checklist when all four core steps are ready, let revoked readiness bring it back, and keep optional watch/setup controls reachable from Settings. Show unpairing only after the server confirms an active relationship, and use the existing archive-and-purge transaction.
- Queue at most five encrypted Smooch sends for at most 15 minutes. Never manufacture delivery after expiration, and keep lock-screen content private by default.
- Select exactly one managed Wear node. Target every active record with a monotonic watch generation; switching or removal must advance the durable target purge barrier before old data can return. Watch-originated Smooches carry no account token and require current target plus relationship generations before the phone may accept ownership.
- Bind each active Wear relationship generation to the source phone node that delivered its first valid managed record. Only that controller may receive watch status/actions or acknowledge/reject queued operations; clear the binding with every relationship purge and 24-hour expiry.
- Keep destructive installer QA on the fixed `com.littleorbit.mobile.smoke` phone/Wear package and shared debug signer. The smoke phone may embed only the generated smoke Wear APK; production and ordinary debug artifacts must exclude the APK, QA label, endpoint, and signing metadata. No installer source may accept an arbitrary target package or signer.
- Register only a random per-install UUID for partner alerts. Use the authenticated first-party WSS hint while an activity is visible and WorkManager polling in the background; never add Firebase, another hosted push SDK, or a provider-issued device address. Fetch authorized event metadata before display, coalesce work without cancelling an active fetch, acknowledge only after Android accepts the notification, and always use a generic public lock-screen version. Scrub retired hosted-transport preferences during upgrade.
- Render the signed-in person's relationship avatar as read-only. Choose, crop, upload, and remove actions always target the current partner, and sign-out or unpair cache cleanup removes both pair-scoped thumbnails.
- Render the signed-in person's relationship name as read-only. Name edits and resets always target the current partner, persist one encrypted stable operation before network use, refresh on revision conflict, and purge both resolved names from phone/Wear caches on sign-out or unpair.
- Use Android-compatible Java library calls across minSdk 29. Countdown reminders use only the fixed server offsets, treat all-day events as 9:00 AM in their IANA timezone, and reconcile after sync, reboot, app replacement, clock changes, or timezone changes.
- Calendar export uses a user-approved insert intent. Never request a Google credential, read calendar data, or present the one-way copy as synchronization.
- Release APKs require all four `ANDROID_SIGNING_*` values, use the same protected key for phone and Wear OS, and must pass `apksigner verify` before publication. Never commit or replace the private release key.
- Build against Android SDK 37 with Java 17 source. Keep target SDK 36 until the Android 17 local-network permission migration is designed and tested.
- Wireless-ADB pairing uses public Conscrypt APIs and authenticated commands. Never add hidden-API access, log pairing material, trust a pre-command Kadb connection flag, or publish values copied from the wrong module's output metadata.
- Keep one stable create operation for each new Our Space workspace and persist it synchronously before the first request. Autosave after 800 ms idle and at least every five seconds during continuous typing, serialize create/title/body mutations, and preserve the accepted server identity through process death or a lost response. A newer server revision requires explicit merge, fork-copy, or shared-version recovery.
- Re-arm privacy-gated location work after sign-in and signed-in process start. Start continuous sampling only with foreground/background permission and both server consents; a lone sample stream must render stale and must never advance nearby time. The visible detail timer anchors server seconds to `elapsedRealtime`, polls for authoritative state, and freezes at the server-provided deadline.
- Treat a wireless-ADB pairing code as transient: never save, autofill, log, or include it in diagnostics. While manual fields are visible, typed host and ports remain authoritative and discovery callbacks must not overwrite them.
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
.\infra\scripts\build-signed-android.ps1 -ReuseWearApk data\releases\<prior-wear>.apk
.\infra\scripts\android-smoke.ps1 -Serial <emulator-serial> -AccountIndex 0 -ResetApp
./gradlew -PwearTestBuildType=smoke :apps:android:wear:connectedSmokeAndroidTest
./gradlew -PmobileTestBuildType=smoke :apps:android:mobile:connectedSmokeAndroidTest
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
