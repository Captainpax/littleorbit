# Home deployment runbook

Public availability depends on this computer, home power, internet service, router, and the Nginx Proxy Manager host remaining online. This topology is suitable for learning and a small service only after security, backup, and device release gates pass.

## Before touching live routing

1. Reserve `192.168.50.182` for this computer's network adapter in router DHCP and verify the lease after reconnect/reboot.
2. Copy `.env.example` to a protected `.env`, generate independent random secrets, configure production SMTP, and replace GitHub placeholders.
3. Run tests, build containers, migrate a fresh database, start the stack, and verify `http://192.168.50.182:8180/api/v1/health/ready` from the NPM host.
4. Restore the newest backup into an empty test database and perform a login smoke test.
5. Verify DNS for `lil-orb.pax-kun.com` without modifying unrelated records.

Promote the first owner only after that person has registered and verified their email:

```powershell
docker compose --env-file .env -f infra/compose.yaml exec api python -m little_orbit_api.cli promote-admin owner@example.com
```

Then visit `/admin/enroll`, re-enter the owner password, scan the TOTP QR code, confirm one current code, and store the one-time recovery codes. The command never creates an account or bypasses email verification.

## Windows Firewall

Create an inbound TCP rule for local port 8180 scoped to remote address `192.168.50.6`. Remove or disable any broader prior rule for the same application port. Verify another LAN host cannot connect while NPM can. Record the actual rule name in private operations notes.

From an elevated PowerShell prompt, apply the repository's idempotent rule:

```powershell
.\infra\scripts\configure-windows-firewall.ps1
```

Use `-WhatIf` to preview the named rule. The script creates or updates only `Little Orbit Gateway - NPM only` and leaves unrelated rules unchanged.

## Nginx Proxy Manager

Create one proxy host for `lil-orb.pax-kun.com`:

- Scheme: HTTP
- Forward hostname/IP: `192.168.50.182`
- Forward port: `8180`
- WebSocket support: enabled
- Block common exploits: enabled
- Certificate: Let's Encrypt for the exact hostname
- Force SSL and HTTP/2: enabled after certificate issuance succeeds

Keep `REGISTRATION_OPEN=false` while Mailpit is the configured SMTP service. Open registration only after an external SMTP delivery test confirms that verification and password-reset links use the public HTTPS origin.

Test website pages, `/api/v1/health/ready`, a real WebSocket upgrade, signup email delivery, and certificate renewal/recovery. Enable HSTS only after those checks and a rollback path succeed. The initial live NPM change is an explicit deployment action; screenshots or a saved draft are not proof that traffic works.

## Restart recovery

Set Docker Desktop/engine and the Compose stack to start after host reboot. Reboot the host, then verify DHCP address, firewall scope, all health checks, public HTTPS, WSS, email, worker schedules, and one curated fallback pool while Ollama is stopped.

## Signed Android releases

Keep the PKCS12 release store and its four `ANDROID_SIGNING_*` settings outside Git. Back them up separately because Android will reject an update signed by a replacement key. Increment `versionCode` before every published update, set the intended `versionName`, then build and verify both targets:

```powershell
.\infra\scripts\build-signed-android.ps1
```

The script loads signing values from the ignored `.env.android-signing`, which Compose never reads. It fails when any value or the store is missing, builds phone and Wear OS release APKs, verifies each signature with the newest installed Android `apksigner`, requires the same certificate on both, and writes APK plus SHA-256 files under `dist/android/`.

Publish in this order:

1. Build, hash, and verify both APKs locally.
2. Commit the final release code and documentation. Create the immutable GitHub tag and upload the exact APK/checksum files as a recovery mirror.
3. Copy the phone and Wear APKs to `data/releases/little-orbit-{version}.apk` and `data/releases/little-orbit-wear-{version}.apk`. Never commit this ignored directory.
4. Update the verified fallback in `apps/web/src/lib/release.ts` with the same version codes, API paths, release URL, byte counts, and SHA-256 values, then deploy the API and rebuilt web image. Compose mounts release storage read-only.
5. Publish the release record. Publication verifies the local file's size and SHA-256 before committing metadata:

```powershell
docker compose --env-file .env -f infra/compose.yaml exec api python -m little_orbit_api.cli publish-release `
  --version 1.0.0-rc.6 `
  --apk-url https://lil-orb.pax-kun.com/api/v1/releases/1.0.0-rc.6/apk `
  --github-release-url https://github.com/Captainpax/littleorbit/releases/tag/v1.0.0-rc.6 `
  --sha256 71093232e3d3dc5c0523a785ad9314de2fa14a0338ef5c9ae336962caa9033fc `
  --release-notes "Insets, relationship age, nearby estimates, permissions, widget, and Wear OS." `
  --version-code 6 --size-bytes 15907162 `
  --package-name com.littleorbit.mobile `
  --signer-sha256 43e83a420c7496ce9121339ab5bd6b01a6357161a83a95042ace56855bd89337 `
  --wear-apk-url https://lil-orb.pax-kun.com/api/v1/releases/1.0.0-rc.6/wear-apk `
  --wear-sha256 857197277ac5da7c23db816ae8dd04f95defa137c4870a0cb1ef2abbac086027 `
  --wear-size-bytes 14124686 --wear-package-name com.littleorbit.mobile `
  --wear-version-code 6 --wear-minimum-android 30 `
  --minimum-android 29 --minimum-supported-version-code 6 `
  --required-after <VERIFIED-UTC-INSTANT>
```

Verify both a complete response and a resumed slice through the public proxy. The range request must return `206`, `Content-Range: bytes 0-1023/15823790`, and exactly 1,024 bytes:

```powershell
curl.exe -fSI https://lil-orb.pax-kun.com/api/v1/releases/1.0.0-rc.6/apk
curl.exe -fsS -H "Range: bytes=0-1023" -D - -o range-check.bin https://lil-orb.pax-kun.com/api/v1/releases/1.0.0-rc.6/apk
curl.exe -fSI https://lil-orb.pax-kun.com/api/v1/releases/1.0.0-rc.6/wear-apk
```

Omit `--required-after` for normal optional releases. Replace the placeholder only after the deployed migration, both hosted artifacts, updater discovery, complete/range downloads, and health checks pass. RC6 deliberately moves the floor to version code 6 after those checks. Once a published record exists, corrections require a new version and new tag; the API deliberately rejects edits and unpublishing.

The public certificate and expected fingerprint are documented in [`../signing/README.md`](../signing/README.md).
