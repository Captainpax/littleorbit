# RC10.1 Wear-installer verification — 2026-09-12

This record covers the focused wireless-debug pairing and phone-hosted Wear installation
correction. It does not close the two-phone, battery, accessibility, or complete 1.0
launch gates.

## Findings and corrections

The public RC10 response declares Wear version code 10, but its immutable, hash-matching
Wear APK contains version code 9. The phone verifier correctly stopped before pairing.
RC10.1 emits module-specific values into `release-manifest.json` and supplies a new Wear
version code 10 artifact. RC10 remains unchanged.

Kadb 2.1.4 opens the ADB transport on its first command. The old adapter constructed a
client and immediately called `connectionCheck()`, which therefore returned false after
every successful pairing. RC10.1 sends a bounded authenticated echo before compatibility
queries. A fresh physical pairing then advanced through inspection without `WCONN-06`.

Kadb's one-shot single-APK install committed the test APK but waited indefinitely for a
terminal stream frame on the physical watch. A sync-push experiment also failed to
produce bounded completion. RC10.1 uses Kadb's package-session flow, which separates
create, write, and commit. Two consecutive phone-hosted session installs reached the
explicit success state without a crash.

Android 17 service discovery now uses continuous service-info callbacks, IPv4 preference,
loss handling, and host-plus-network endpoint association. Kadb uses bundled Conscrypt
2.6.0, and its optional hidden-API bypass is absent from the APK.

## Automated and artifact checks

| Area | Check | Result |
|---|---|---|
| Android behavior | Domain, data, mobile, and Wear unit tests; mobile and Wear lint | Passed |
| Focused regressions | Endpoint replacement/loss/network matching and privacy-safe transport classification | Passed |
| Repository limits | `python infra/scripts/check_quality.py` | Passed for 246 source files |
| Signed build | `infra/scripts/build-signed-android.ps1` | Passed; separate phone/Wear metadata manifest emitted |
| Release staging | `infra/scripts/publish-signed-android.ps1` without `-Publish` | Passed; manifest, APK identities, hashes, and signers rechecked |
| APK identity | `aapt dump badging` and `apksigner verify --print-certs` | Phone code 11, Wear code 10, one expected signer |
| Packaging | `zipalign -c -P 16 -v 4` and archive inspection | Both aligned; four Conscrypt native entries; no HiddenApiBypass entry |

The strict final artifacts are:

- Phone: 35,061,635 bytes; SHA-256 `0336d41bb6b6d247b6e12e52fdd9a99c0900602fc0bc5eebac99c3269d74a41b`.
- Wear: 14,130,630 bytes; SHA-256 `89e867ef766cca38c17f7a92927afb4c0c074a1a28fbef672739f15bf3bfced8`.
- Certificate: `43e83a420c7496ce9121339ab5bd6b01a6357161a83a95042ace56855bd89337`.
- Minimum API: phone 29 and Wear 30. Compile SDK is 37; target SDK remains 36.

## Physical-device evidence

The desktop paired with a Pixel Watch 3 on API 37, installed the signed RC10.1 Wear
candidate, launched it, captured the expected stale-data screen, and found no fatal
runtime event. The test app and only the desktop authorization were then removed; the
phone identity was preserved.

A Pixel 8 Pro on API 37 discovered the watch, completed a fresh phone pairing, retained
the encrypted identity, and reached authenticated watch inspection. A local diagnostic
build accepted the known RC10 artifact version code 9 solely so the transport could be
tested before RC10.1 publication. It did not weaken URL, size, hash, package, watch-feature,
or signing-certificate verification. Two package-session installations completed, and a
cold process reconnected without another code. No fatal phone runtime event was found.

All diagnostic-only metadata and same-version policy changes were removed before the
strict signed build. The strict phone APK was installed in place on the Pixel 8 Pro and
reports version code 11 while retaining app data and the phone's watch authorization.
The watch is intentionally left on the public RC10 artifact's actual version code 9 so
the strict RC10.1 code 10 upgrade can be verified after publication.

Pairing codes, local addresses, ports, device fingerprints, private keys, and raw
transport exceptions are omitted. Temporary desktop authorization was removed through
watch settings, and the temporary watch screen-timeout change was restored.

## Documentation inventory and open gate

Every repository-owned Markdown file returned by `rg --files -g '*.md'` was reviewed.
Android, infrastructure, signing, privacy, security, network, contributor, showcase,
roadmap, release, ADR, and Wear operations documents were updated where behavior or
evidence changed. Unrelated product and historical documents remain accurate.

Before publication is called complete:

- copy the strict artifacts into immutable release storage and publish only the generated
  manifest values;
- verify current/history JSON, full and range downloads, download page, patch notes, and
  RSS through public HTTPS;
- use the strict signed phone build to upgrade the physical watch from code 9 to code 10;
- confirm launcher start and a remembered current-version inspection after publication.
