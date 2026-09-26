# ADR 0019: Wear ADB transport compatibility

- Status: accepted for RC10.1
- Date: 2026-09-12
- Extends: ADR 0014

## Context

The RC10 phone installer could complete the wireless-debug pairing exchange but then
reported `WCONN-06`, and its transfer could remain on the sending state even after the
watch had installed the APK. Three independent causes were found on a Pixel 8 Pro and
Pixel Watch 3 running API 37:

1. Kadb 2.1.4 opens its authenticated transport lazily, so `connectionCheck()` is false
   on every newly constructed client until a command is issued.
2. Kadb's one-shot streaming install can commit the APK and then wait indefinitely for
   a terminal stream frame on this Wear build.
3. RC10 metadata declared Wear version code 10, while the immutable RC10 Wear APK
   actually contains version code 9. The strict phone verifier correctly rejected it.

Android 17 also provides continuously updated DNS-SD service information. Treating a
single resolution as permanent can retain an expired wireless-debug port.

## Decision

RC10.1 uses Kadb 2.1.4 behind the existing Java reflection boundary, compiles Android
modules with SDK 37 while retaining target SDK 36, and bundles Conscrypt 2.6.0 for the
public TLS exporter API. Hidden-API bypass code is excluded from the phone package.

The connection proof is an authenticated, bounded `echo` command. Discovery registers
continuous service-info callbacks on supported Android releases, prefers IPv4, removes
lost services, and associates pairing and connection endpoints by host and network.
Older Android releases keep a serialized resolver fallback. Pairing consumes the first
matching post-pair connection endpoint and refreshes rotated ports before retrying.

APK delivery uses Kadb's package-install session API, even for one APK. The session
separates create, write, and commit and avoids the one-shot terminal-frame wait observed
on the physical watch. Package replacement remains enabled; downgrade and uninstall
flags remain forbidden.

The signed build command emits `release-manifest.json` from each module's own Gradle
output metadata. Operators must copy phone and Wear version codes, sizes, hashes, and
the shared signing certificate from that manifest. Published bytes and metadata remain
immutable; a bad release is corrected by a higher version.

## Consequences

The phone APK is larger because it includes Conscrypt native libraries, and its release
build must pass 16 KiB page-alignment verification. Pairing codes, endpoints, device
fingerprints, and raw exception messages stay out of logs and committed verification
records. Android 17 target-SDK local-network permission is deferred until the project
targets SDK 37; compile SDK 37 alone does not change the current permission contract.

Physical RC10.1 validation must cover a fresh pair, a remembered reconnect, a full APK
commit, wrong-code and stale-authorization recovery, service-port rotation, and removal
of a temporary desktop authorization without deleting the phone identity.
