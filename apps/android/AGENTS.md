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
- Location collection requires explicit consent and current permission. Queue bounded, encrypted samples; stop immediately after permission or sharing is revoked.
- Widgets and wear surfaces read a minimal cache containing together-time, next countdown, update instant, and no relationship content.
- Every cached surface shows when data is stale or unavailable.
- Offline changes need stable operation IDs. Preserve note drafts when the server revision diverges.

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
```

Test DTO/domain separation, Room migrations, retries and duplicate work, stale cache rendering, permission removal, clock/timezone boundaries, process death, reboot, unauthorized responses, widget updates, and Wear disconnection.

## Documentation impact

Update SHOWCASE for visible behavior, PRIVACY for permissions/data, NETWORK-FLOW for transport, and an ADR for module or storage changes.

## Common mistakes

- Putting Android types in domain models.
- Sharing Room entities or Retrofit DTOs with UI code.
- Assuming the phone, widget, and watch refresh together.
- Scheduling unbounded work or exact alarms without a product requirement.
- Treating a location permission grant as consent to share.
