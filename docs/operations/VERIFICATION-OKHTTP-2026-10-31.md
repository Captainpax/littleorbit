# Focused OkHttp security assessment - October 31, 2026

## Source and change

Assessed default-branch commit `2bca90e64d11b44562b3e9678a387295fe8f0873`.
The only dependency change is `gradle/libs.versions.toml`: the shared `okhttp`
version moves from `5.5.0` to `5.5.1`. Both `com.squareup.okhttp3:okhttp` and
`com.squareup.okhttp3:logging-interceptor` use that version reference. No lockfile
or Gradle dependency-verification metadata is tracked. The other updates in
[Dependabot PR 44](https://github.com/Captainpax/littleorbit/pull/44) are excluded.

The [upstream 5.5.1 changelog](https://github.com/lysine-dev/okhttp/blob/parent-5.5.1/CHANGELOG.md)
dates the release to October 22, 2026. The
[5.5.0-to-5.5.1 comparison](https://github.com/lysine-dev/okhttp/compare/parent-5.5.0...parent-5.5.1)
contains the certificate-blocklist fix and release preparation. The
[fix and upstream regression](https://github.com/lysine-dev/okhttp/commit/6db98026dfb817a23c0282aa4e53d8187b309052)
reject peer chains containing any of eight compromised eMudhra intermediate
public keys. Its local TLS-server test checks rejection before an HTTP request
is received. That upstream test was reviewed, not executed in this checkout.

## Applicability

- [DisplayModule.java](../../apps/android/data/src/main/java/com/littleorbit/data/DisplayModule.java) builds the shared client with
  `OkHttpClient.Builder().addInterceptor(sessions).build()`. No custom trust
  manager, hostname verifier, SSL socket factory, or certificate pinner appears
  in Android source. Retrofit uses that same client.
- [NoteSocketClient](../../apps/android/data/src/main/java/com/littleorbit/data/remote/NoteSocketClient.java),
  [ForegroundNotificationSocket](../../apps/android/mobile/src/main/java/com/littleorbit/mobile/ForegroundNotificationSocket.java), and
  [ProductionWearReleaseClient](../../apps/android/mobile/src/main/java/com/littleorbit/mobile/ProductionWearReleaseClient.java) use it for note WSS, notification WSS, and the
  phone-hosted Wear APK HTTPS download. The data and phone modules declare
  OkHttp; the widget reaches it through data. Wear does not directly declare it.
- [AndroidUpdateCoordinator](../../apps/android/mobile/src/main/java/com/littleorbit/mobile/AndroidUpdateCoordinator.java) downloads the phone's own APK through Android
  DownloadManager. Its platform TLS path is outside this library update.
- [Google's incident notice](https://blog.google/security/protecting-chrome-and-android-users-from-compromised-emudhra-intermediate-ca-certificates/)
  describes automatic protection delivered through Play Services. A device that
  received that update already has equivalent protection. AOSP devices and JVMs
  that still trust the compromised hierarchy benefit from OkHttp's blocklist;
  this repository's affected production client is Android.

Source configuration cannot establish which dependency is inside an installed
APK, whether a device received the Play Services update, or the certificate
chain served to that device. No installed APK, device trust store, production
endpoint, private account, or live recovery system was inspected.

## Local validation

Validated locally on Windows with Temurin Java 17.0.20.1, Gradle 9.7.1,
Android SDK platform 37.0 revision 2 and build-tools 37.0.0.

| Check | Result |
| --- | --- |
| Phone `debugRuntimeClasspath` dependency insight | OkHttp, okhttp-android and logging-interceptor resolve to 5.5.1; Retrofit's 4.12.0 request selects 5.5.1 |
| Phone `releaseRuntimeClasspath` dependency insight | Same selected 5.5.1 versions, with no unresolved OkHttp components |
| Domain unit tests | 22 passed, no failures/errors/skips |
| Data debug unit tests | 31 passed, no failures/errors/skips |
| Phone debug unit tests | 58 passed, no failures/errors/skips |
| Data and phone debug lint | Passed; 5 and 126 warnings respectively, no errors/fatal findings; warnings were not triaged in this dependency-only change |
| Phone debug assembly | Passed; all changed dependencies packaged successfully |
| Built debug APK inspection | `okhttp/5.5.1` user-agent marker present in `classes14.dex`; supplementary packaging evidence, not a certificate-rejection test |
| Documentation inventory and local links | Passed, 139 files including this new record |
| Markdown lint | Passed for all 139 Markdown files |
| Release-train consistency and `git diff --check` | Passed |

The final Android invocation completed successfully with 149 actionable tasks
(112 executed, 37 from cache):

```powershell
.\gradlew.bat :apps:android:mobile:dependencyInsight --configuration releaseRuntimeClasspath --dependency com.squareup.okhttp3 :apps:android:domain:test :apps:android:data:testDebugUnitTest :apps:android:data:lintDebug :apps:android:mobile:testDebugUnitTest :apps:android:mobile:lintDebug :apps:android:mobile:assembleDebug --no-daemon --console=plain
```

The debug dependency check used the same `dependencyInsight` task with
`--configuration debugRuntimeClasspath`. Documentation checks were
`python infra/scripts/check_docs.py`, `python infra/scripts/check_versions.py`,
`npx --yes markdownlint-cli2 "**/*.md"`, and `git diff --check`.

An initial offline dependency report could not resolve uncached 5.5.1 artifacts;
the subsequent online report resolved them. The first combined Android attempt
stopped before tests because Java 17 was not auto-detected; explicitly selecting
the installed Java 17 toolchain resolved it. An intermediate command used a
nonexistent `dependencyInsightRelease` task and was corrected to the standard
task with `--configuration releaseRuntimeClasspath`. These were environment or
command setup failures, not failing application tests. The required SDK 37
platform was installed using the SDK's already accepted license. Gradle also
reported deprecated build APIs and unstripped native-library packaging warnings.

Local evidence is retained under ignored `.inspect/`:

- `okhttp-debug-dependencies.log`
- `okhttp-android-java17-validation.log`
- `okhttp-markdownlint.log`
- `okhttp-validation-summary.json`

Not run: the upstream compromised-certificate TLS regression, Wear-specific
tests/lint/assembly, connected Android/emulator matrix, isolated paired-account
smoke flow, release signing/publication, or live service/recovery checks. The
separately reported recovery-profile CI issue was not rerun or changed and is
not evidence about this Android patch.

## Documentation and release boundary

Inventoried all 138 pre-existing repository-owned Markdown files. Updated the
roadmap, security boundary, transport prose, third-party notices, and inventory,
and added this verification record. Privacy/data handling, route topology,
public feature descriptions, contributor workflow, accepted ADRs, and historical
release/verification records remain accurate for this dependency-only change.
No diagram topology changed. The pre-existing Conscrypt version prose differs
from its catalog pin and is outside this focused OkHttp update.

This is an unreleased source preparation. Product version `1.3.0`, phone version
code `29`, and Wear version code `21` are unchanged. A debug APK was built solely
for local validation; no release-signed artifact was created or published, no
branch was pushed, and no pull request was opened.
Before publication, complete outstanding Android validation and device checks,
increase the phone version code, build/sign through the existing isolated release
workflow, verify generated artifact metadata and signing identity, and obtain
separate approval for publication. Existing published APKs remain immutable.
