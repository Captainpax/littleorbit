# Phone-hosted Wear installer runbook

Little Orbit installs its self-hosted Wear companion from the Android phone app. No PowerShell script or Play Store listing is required.

## Person-facing flow

1. Put the phone and watch on the same trusted Wi-Fi network.
2. On the watch, enable developer options and wireless debugging, then choose **Pair new device**.
3. On the phone, open Little Orbit, choose **Settings** > **Watch settings**, choose the connected watch, then choose **Install or update watch app**.
4. Allow nearby-device discovery when asked, or open the manual fields and enter the watch host, pairing port, and connection port. Values you type stay selected until you choose **Scan again**.
5. Enter the six-digit code shown by the watch and explicitly continue. Only this action downloads and verifies the Wear APK; opening the page and background update checks fetch metadata only.
6. If the watch patch is unknown or older than May 1, 2026, read the warning and either cancel or explicitly continue.
7. Wait for **Little Orbit is installed on your watch**, then disable wireless debugging on the watch.

The phone keeps its ADB identity encrypted so later Little Orbit Wear updates normally reconnect without a new pairing code. The same wizard has install/update, repair/reinstall, and private-removal modes. **Forget watch authorization** deletes only the local identity. Private removal additionally advances the managed-watch purge barrier, clears watch-originated queued Smooches, uninstalls Little Orbit from the confirmed watch, forgets the local identity, and tells the person to disable wireless debugging and remove the phone from the watch's paired debugging devices. The watch may still list an old authorization until that watch-side step is completed. A remembered authorization is proven with a harmless authenticated command before device properties are read.

The watch can change its TLS connection port after pairing. Leave the wireless-debug screen open until installation finishes. RC10.1 tracks current DNS-SD service information, removes lost services, keeps pairing and connection endpoints on the same host and network, prefers IPv4, and refreshes the active connection port after pairing. The APK is installed through an explicit package session so write and commit completion are distinct. If discovery remains incomplete, enter the current pairing and connection ports shown on the watch; do not reuse a port from an earlier wireless-debug session.

The six-digit code is intentionally temporary. The phone disables autofill and saved view state for that field, clears it immediately after copying it into the in-memory pairing request, clears it again when the installer leaves the screen, and redacts it from request diagnostics. If signed metadata or APK preparation fails before watch contact, choose **Try download again**; that explicit retry repeats download and verification before watch contact. Pairing codes and APK downloads are never background work.

## Watch settings and mixed versions

The phone authorizes exactly one managed Data Layer node. Switching watches advances a monotonic target generation so the previous watch purges its display, names, thumbnails, configuration, and queued actions before the new target is populated. Photos, countdown titles, watch Smooches, update alerts, and the default destination start enabled only after explicit watch selection. Disabling watch Smooches also removes queued watch-originated requests.

A 1.1.0 phone retires legacy global payloads, so a 1.0.1 Wear companion becomes unavailable and Watch settings directs the person to install/update. A 1.1.0 companion paired with a 1.0.1 phone may render the legacy passive cache, but watch Smooches remain disabled because no target-scoped configuration has authorized them.

## Verification checklist

- Metadata and APK URL use the exact current versioned `lil-orb.pax-kun.com` HTTPS endpoint.
- Downloaded byte count, SHA-256, package, version, watch feature, and signing certificate match published metadata.
- Discovery grant finds both endpoints from one host; discovery denial exposes manual fields without a crash.
- A late discovery callback cannot replace visible manual values; **Scan again** returns to newly discovered values.
- Starting discovery twice cannot let the first attempt overwrite the second, and a post-pair port change is used for install.
- A wrong pairing code fails without logging the code; retry with a new code works.
- Rotation, backgrounding, view-state restore, and autofill never restore a pairing code; request diagnostics remain redacted.
- Signed-artifact preparation failure exposes one retry action and cannot enable installation with an unverified file.
- Opening Settings, Watch settings, or the installer performs no APK download. Metadata-only update discovery cannot pair, install, repair, remove, or download bytes.
- A phone target, unsupported watch SDK, same version, and higher installed version produce their respective safe outcomes.
- An old or unreadable patch level warns and cancel performs no install.
- A current patch installs with replace only; no downgrade or uninstall flag is used.
- A second update reconnects through the encrypted identity; forgetting it requires pairing again.
- Repair reinstalls the same verified current version only after an explicit action; normal update reports an already-current version without reinstalling it.
- Private removal purges with a newer watch generation before uninstall, removes only `com.littleorbit.mobile`, clears watch-originated queue entries, forgets the local key after success, and provides watch-side revocation guidance.
- Android reports a committed package before the success screen; a transfer that never receives commit confirmation remains a failure.
- The installed Together, Countdown, and Smooch destinations, tile, Nearby complication, Countdown complication, preferences, and profile synchronization work after wireless debugging is disabled.
- A watch Smooch requires picker plus confirmation, survives a short disconnect under one stable UUID, transfers ownership once, expires at 15 minutes, and cannot cross a target switch, relationship purge, or preference revocation.
- Sign-out, unpair, deletion, and an inactive-relationship response purge launcher, tile, complication, names, and thumbnails when connected. A disconnected watch shows stale after six hours, deletes relationship state at 24 hours, and rejects delayed pre-purge records.
- Stage text distinguishes discovery, pairing, TLS transition, device inspection, verification, and installation so a failure can be reported without addresses or codes.

Do not capture pairing codes, local watch addresses, private keys, profile photos, or device identifiers in issue reports. Record only a sanitized outcome and OS/API level.
