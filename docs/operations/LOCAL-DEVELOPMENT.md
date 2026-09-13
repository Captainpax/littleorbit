# Local development

## Requirements

- Docker Desktop with Compose 5+
- Node.js 24+ and npm 11+
- Python 3.12 or 3.13 (the pinned native dependencies do not yet support 3.14)
- Java 17, Android SDK 37, and an Android emulator for client work

Copy `.env.example` to `.env` and replace every `change-me`, `replace-`, and placeholder repository URL. Development may use localhost URLs and Mailpit. Never reuse these values publicly.

```powershell
docker compose --env-file .env -f infra/compose.yaml -f infra/compose.dev.yaml config
docker compose --env-file .env -f infra/compose.yaml -f infra/compose.dev.yaml up --build
Invoke-WebRequest http://localhost:8180/api/v1/health/ready
```

Open `http://localhost:8180` for the website and `http://localhost:8025` for development email. Stop containers with `docker compose --env-file .env -f infra/compose.yaml -f infra/compose.dev.yaml stop`; do not delete volumes during routine work.

The first model initialization downloads roughly 2.5 GB. Add `-f infra/compose.gpu.yaml` only after NVIDIA container support works in Docker Desktop. CPU fallback is slower but retains curated-question coverage.

## Our Space attachment development

The API writes uploads to the private `attachment-data` volume. `media-worker` streams pending bytes to the internal-only `clamav` service, then rebuilds images and PDFs or remuxes audio/video before marking them available. ClamAV can take about 90 seconds to download definitions and become healthy on its first start. Scanner or sanitizer failure leaves content unavailable.

Use synthetic files. Exercise JPEG/PNG/WebP/GIF, PDF, TXT/Markdown, MP3/M4A/Ogg, and MP4/WebM; unsupported extensions and misleading media types must fail. Cover a missing `Content-Length`, chunks above 4 MiB, gaps, replayed operation IDs with different metadata, an original hash mismatch, malware detection, scanner outage, metadata removal, the 100 MiB file limit, the 2 GiB couple quota, explicit delete, and expired-note cleanup. Android must verify the post-sanitization size and hash, preview from **Keep offline** without a network, and clear private copies after deletion or relationship state changes.

```powershell
docker compose --env-file .env -f infra/compose.yaml -f infra/compose.dev.yaml ps
docker compose --env-file .env -f infra/compose.yaml logs media-worker clamav
.\.venv313\Scripts\python.exe -m pytest services/api/tests/test_note_attachments.py
```

Do not paste filenames, attachment bytes, local cache paths, or relationship content into logs or bug reports.

## Android updater development

The phone requests `https://lil-orb.pax-kun.com/api/v1/releases/current` and accepts only the matching versioned API APK endpoint or a historical canonical GitHub release asset. Create `data/releases/` and copy a signed APK there using `little-orbit-{version}.apk`; Compose mounts that ignored directory read-only into the API. Test pure policy and restart behavior without a device:

```powershell
.\gradlew.bat :apps:android:domain:test :apps:android:mobile:testDebugUnitTest
```

End-to-end installation needs a signed older build on an emulator or test phone and a newer, already-published test release using the same signing certificate. Never weaken URL, hash, package, version, or certificate checks to make a local fake APK pass. A first install may require Android's **Install unknown apps** permission; the app requests it only after the person starts an update.

RC10 asks once whether optional metadata discovery should run, schedules checks about every six hours when enabled, and keeps required-floor checks active. Validate that the worker never creates a DownloadManager request, Later suppresses only the current process, and a running or paused transfer with no progress for five minutes becomes stalled.

## Phone-hosted Wear installer development

The More-tab installer uses Wear OS wireless debugging directly from the phone. The phone and watch must be on the same trusted Wi-Fi network. On the watch, enable developer options, wireless debugging, and **Pair new device**, then enter the displayed six-digit code in the phone app. Android 13 and later may request nearby-device permission for DNS-SD discovery; manual host and ports remain available after denial. Android 17 local-network permission becomes relevant when the app targets SDK 37; RC10.1 compiles with SDK 37 but still targets SDK 36.

The phone downloads only the exact `wear_apk_url` from current release metadata. Before pairing it verifies size, SHA-256, package, version, required watch feature, and the pinned signer. After pairing it rejects phones, unsupported SDKs, and downgrades. A missing or pre-May-2026 watch patch level must show a user-overridable warning. Test the pure policy with:

```powershell
.\gradlew.bat :apps:android:mobile:testDebugUnitTest --tests "com.littleorbit.mobile.WearInstallPolicyTest"
```

Kadb 2.1.4 is isolated behind `KadbWatchClient` because its published Android bytecode targets Java 21 while Little Orbit production source stays Java 17. Android modules compile with SDK 37. The phone bundles Conscrypt 2.6.0 and excludes HiddenApiBypass so pairing uses a public TLS exporter API. Do not import Kadb types outside that adapter or increase either dependency without checking bytecode, compile-SDK metadata, native-library page alignment, license, and a physical pairing/install flow. Turn off wireless debugging on the watch after testing and use **Forget watch authorization** before handing a device to someone else.

When reproducing pairing failures, keep the watch's wireless-debug page visible and record only the named stage and safe `WPAIR`, `WCONN`, `WINFO`, or `WINST` code. Test continuous service updates, loss and port rotation, an authenticated first command, fresh pairing, remembered authorization, package-session commit, and manual entry. Kadb establishes connections lazily, so `connectionCheck()` cannot prove a newly created client is authorized. Never record the host, ports, pairing code, fingerprint, raw exception, or key material in committed logs.

## Smooch and proximity development

Use two disposable verified accounts for delivery tests. Cover the sixth send inside a rolling hour, exact hour expiry, duplicate operation IDs, a queued send older than 15 minutes, notification privacy, DST week boundaries, unpair archives, repairing isolation, and either account's deletion. Do not place message content in admin fixtures.

Location testing requires both the Android runtime permission and both accounts' in-app consent. Confirm the foreground-service notification remains visible, the first fix is requested promptly, WorkManager can queue while offline, and either consent or permission removal stops the service and clears local samples. Server acceptance proves only that a sample arrived; only two consecutive accurate, nearby matched pairs can establish estimated nearby time.

## Profile photo development

Use synthetic images only. The server accepts JPEG, PNG, and WebP up to 5 MiB, rejects animation and decompression bombs, removes source metadata, and emits 512-pixel plus 128-pixel WebP variants. Verify owner fetch, current-partner fetch, unpaired rejection, delete/re-add cache invalidation, account export, and Wear launcher synchronization. Never add profile image fixtures containing a real person.
