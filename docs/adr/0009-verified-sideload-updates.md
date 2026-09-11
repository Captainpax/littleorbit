# ADR 0009: Verified user-approved sideload updates

- Status: Accepted
- Date: 2026-09-11

## Context

Little Orbit distributes its free Android build through GitHub Releases. People who install that APK need a clear path to later versions without trusting a second download host or allowing the app to install code silently. The server may eventually reject obsolete protocol versions, but a routine feature release must not lock someone out merely because it exists.

## Decision

The public API exposes one immutable published release record containing the increasing Android `versionCode`, canonical GitHub APK and release URLs, exact byte count, SHA-256, package name, signing-certificate SHA-256, minimum Android API, compatibility floor, optional UTC enforcement time, and release notes.

The phone checks metadata at launch and through a daily network-constrained worker. The worker downloads metadata only. An optional update appears in the app and may be deferred for 24 hours. The APK download begins only after the person taps **Update now**.

Android `DownloadManager` owns the transfer. Before opening `PackageInstaller`, Little Orbit verifies all of these properties:

1. the URL belongs to the exact `Captainpax/littleorbit` GitHub release tag;
2. file length and SHA-256 match the immutable release record;
3. the archive package is `com.littleorbit.mobile`;
4. its version code exactly matches the record and is newer than the installed app; and
5. its signing history contains the certificate fingerprint pinned in the app.

Android always presents its installation approval UI. Updater phases, exact release identity, progress, and safe failure codes are persisted so activity recreation and process death can reconcile with Android-owned work. A different release cannot reuse an earlier download or install session.

A compatibility floor is inactive until an administrator supplies a timezone-aware `required_after` instant. After that instant, HTTP mobile routes return `426 client_update_required` and note WebSockets close with code `4426` before authentication or protected lookup. The phone blocks ordinary use only when its installed version is below that active floor. Wear OS continues through Android's paired-device or store update flow; the phone never transfers an APK to the watch.

## Consequences

- GitHub remains the only APK byte host, so the home server does not carry release bandwidth.
- Compromise of release metadata alone cannot substitute an APK signed by another certificate.
- The private signing key remains a critical long-term backup; replacing it breaks upgrades.
- The first build containing this updater must still be installed manually by existing RC2 users.
- Operators must publish and verify immutable GitHub bytes before inserting their metadata.
- Required updates remain an emergency compatibility tool with an explicit activation time, not a routine release mechanism.
