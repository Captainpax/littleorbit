# Phone-hosted Wear installer runbook

Little Orbit installs its self-hosted Wear companion from the Android phone app. No PowerShell script or Play Store listing is required.

## Person-facing flow

1. Put the phone and watch on the same trusted Wi-Fi network.
2. On the watch, enable developer options and wireless debugging, then choose **Pair new device**.
3. On the phone, open Little Orbit, choose **More**, then **Install on watch**.
4. Allow nearby-device discovery when asked, or open the manual fields and enter the watch host, pairing port, and connection port.
5. Enter the six-digit code shown by the watch and choose **Install on watch**.
6. If the watch patch is unknown or older than May 1, 2026, read the warning and either cancel or explicitly continue.
7. Wait for **Little Orbit is installed on your watch**, then disable wireless debugging on the watch.

The phone keeps its ADB identity encrypted so later Little Orbit Wear updates normally reconnect without a new pairing code. **Forget watch authorization** deletes that local identity. The watch may still list the old authorization until it is removed in watch developer settings.

## Verification checklist

- Metadata and APK URL use the exact current versioned `lil-orb.pax-kun.com` HTTPS endpoint.
- Downloaded byte count, SHA-256, package, version, watch feature, and signing certificate match published metadata.
- Discovery grant finds both endpoints from one host; discovery denial exposes manual fields without a crash.
- A wrong pairing code fails without logging the code; retry with a new code works.
- A phone target, unsupported watch SDK, same version, and higher installed version produce their respective safe outcomes.
- An old or unreadable patch level warns and cancel performs no install.
- A current patch installs with replace only; no downgrade or uninstall flag is used.
- A second update reconnects through the encrypted identity; forgetting it requires pairing again.
- The installed launcher, tile, complication, and profile synchronization work after wireless debugging is disabled.

Do not capture pairing codes, local watch addresses, private keys, profile photos, or device identifiers in issue reports. Record only a sanitized outcome and OS/API level.
