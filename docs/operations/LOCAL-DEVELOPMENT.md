# Local development

## Requirements

- Docker Desktop with Compose 5+
- Node.js 24+ and npm 11+
- Python 3.12 or 3.13 (the pinned native dependencies do not yet support 3.14)
- Java 17, Android SDK 36, and an Android emulator for client work

Copy `.env.example` to `.env` and replace every `change-me`, `replace-`, and placeholder repository URL. Development may use localhost URLs and Mailpit. Never reuse these values publicly.

```powershell
docker compose --env-file .env -f infra/compose.yaml -f infra/compose.dev.yaml config
docker compose --env-file .env -f infra/compose.yaml -f infra/compose.dev.yaml up --build
Invoke-WebRequest http://localhost:8180/api/v1/health/ready
```

Open `http://localhost:8180` for the website and `http://localhost:8025` for development email. Stop containers with `docker compose --env-file .env -f infra/compose.yaml -f infra/compose.dev.yaml stop`; do not delete volumes during routine work.

The first model initialization downloads roughly 2.5 GB. Add `-f infra/compose.gpu.yaml` only after NVIDIA container support works in Docker Desktop. CPU fallback is slower but retains curated-question coverage.

## Android updater development

The phone requests `https://lil-orb.pax-kun.com/api/v1/releases/current` and accepts only the matching versioned API APK endpoint or a historical canonical GitHub release asset. Create `data/releases/` and copy a signed APK there using `little-orbit-{version}.apk`; Compose mounts that ignored directory read-only into the API. Test pure policy and restart behavior without a device:

```powershell
.\gradlew.bat :apps:android:domain:test :apps:android:mobile:testDebugUnitTest
```

End-to-end installation needs a signed older build on an emulator or test phone and a newer, already-published test release using the same signing certificate. Never weaken URL, hash, package, version, or certificate checks to make a local fake APK pass. A first install may require Android's **Install unknown apps** permission; the app requests it only after the person starts an update.

## Phone-hosted Wear installer development

The More-tab installer uses Wear OS wireless debugging directly from the phone. The phone and watch must be on the same trusted Wi-Fi network. On the watch, enable developer options, wireless debugging, and **Pair new device**, then enter the displayed six-digit code in the phone app. Android 13 and later may request nearby-device permission for DNS-SD discovery; manual host and ports remain available after denial.

The phone downloads only the exact `wear_apk_url` from current release metadata. Before pairing it verifies size, SHA-256, package, version, required watch feature, and the pinned signer. After pairing it rejects phones, unsupported SDKs, and downgrades. A missing or pre-May-2026 watch patch level must show a user-overridable warning. Test the pure policy with:

```powershell
.\gradlew.bat :apps:android:mobile:testDebugUnitTest --tests "com.littleorbit.mobile.WearInstallPolicyTest"
```

Kadb 2.1.1 is isolated behind `KadbWatchClient` because its published Android bytecode targets Java 21 while Little Orbit production source stays Java 17 and compileSdk 36. Do not import Kadb types outside that adapter or increase its version without checking bytecode, compileSdk metadata, license, and a physical pairing/install flow. Turn off wireless debugging on the watch after testing and use **Forget watch authorization** before handing a device to someone else.

## Profile photo development

Use synthetic images only. The server accepts JPEG, PNG, and WebP up to 5 MiB, rejects animation and decompression bombs, removes source metadata, and emits 512-pixel plus 128-pixel WebP variants. Verify owner fetch, current-partner fetch, unpaired rejection, delete/re-add cache invalidation, account export, and Wear launcher synchronization. Never add profile image fixtures containing a real person.
