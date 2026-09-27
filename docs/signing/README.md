# Android signing identity

Little Orbit phone and Wear OS release APKs use the same update identity. The private key is stored outside Git and must remain available for every future update.

- Subject: `CN=Little Orbit Release, OU=Open Source, O=Little Orbit, C=US`
- Key: RSA 4096-bit with SHA-256
- Validity: 2026-09-11 through 2051-09-05
- Certificate SHA-256: `43e83a420c7496ce9121339ab5bd6b01a6357161a83a95042ace56855bd89337`
- Public certificate: [`little-orbit-release-cert.pem`](little-orbit-release-cert.pem)

Verify a downloaded APK with Android SDK Build Tools:

```powershell
apksigner verify --verbose --print-certs little-orbit-1.0.0-rc.4.apk
```

The command must report that the APK verifies and that its certificate SHA-256 exactly matches this document. Also compare the APK file SHA-256 with the value on the Little Orbit download page and its mirrored `.sha256` GitHub asset.

`infra/scripts/build-signed-android.ps1` remains the Windows recovery workflow. It writes
`release-manifest.json` beside the two signed APKs, reads phone and Wear version codes from their
separate Gradle metadata files, rejects any signer other than the certificate pinned above, and
requires the Wear artifact to declare `android.hardware.type.watch`. Publication rechecks that
feature before staging bytes.
Do not assume the two modules share a version code. Published metadata and bytes are immutable, so
any mismatch requires a higher corrective release.

## Isolated `.14` release workflow

The operational release host uses the files under `android-release/`. It builds two separate
images from a digest-pinned JDK 17 base and captures each resulting `sha256:` image ID before any
container starts. Every builder and signer invocation uses that immutable ID rather than the
mutable convenience tag:

- The builder has network access for Gradle dependencies but receives only a clean `git archive` of
  the committed checkout. It never receives ignored files, an environment file, or a keystore.
- The signer runs with `--network none`, a read-only root filesystem, every Linux capability
  dropped, `no-new-privileges`, and no Docker socket. Candidate and signer inputs are read-only;
  scratch space is tmpfs.

The images pin Android command-line tools 20.0, SDK platform 37 revision 2, Build Tools 37.0.0,
AGP 9.4.0, and Gradle 9.7.1. Ordinary Gradle release tasks remain fail-closed without all four
`ANDROID_SIGNING_*` values. The only unsigned exception requires both the environment marker and
root-owned marker file baked into the isolated builder image.

Create the encrypted bundle on the existing protected signing host. The helper reads the legacy
environment and keystore into memory, writes no plaintext archive, refuses output inside Git, and
passes the archive directly to `age`:

```powershell
python android-release/create_signer_bundle.py `
  --environment C:\protected\little-orbit-signing.env `
  --recipient age1... `
  --output C:\protected\little-orbit-signer.tar.age
```

The helper resolves a bare `age` executable once from `PATH`; use
`--age-bin /absolute/path/to/age` (or `ANDROID_RELEASE_AGE_BIN`) for the pinned `.14` binary. A
relative path containing directories is rejected.

Transfer only the encrypted bundle to
`/mnt/cache/vault/little-orbit/android-signing/little-orbit-signer.tar.age`. Keep the age identity
root-only outside the repository. Both files must be owned by root with mode `0400` or `0600`. On
`.14`, start from the clean committed checkout and two new, empty work directories:

```bash
sh android-release/run-release.sh \
  /mnt/cache/little-orbit-deploy/repo \
  /mnt/cache/little-orbit-live/release-work/little-orbit/candidate-<run-id> \
  /mnt/cache/little-orbit-live/release-work/little-orbit/signed-<run-id> \
  /mnt/cache/vault/little-orbit/android-signing/little-orbit-signer.tar.age \
  /mnt/cache/little-orbit-secrets/android-signing-age-identity.txt
```

The runner uses the checksum-pinned age binary at
`/mnt/cache/little-orbit-tools/bin/age`. A recovery installation at another absolute path must be
selected explicitly with `ANDROID_RELEASE_AGE_BIN=/absolute/path/to/age`; relative or `PATH`-only
selection is rejected.

Restore-check an encrypted production bundle without creating, signing, or writing any APK:

```bash
sh android-release/run-release.sh --verify-bundle \
  /mnt/cache/little-orbit-deploy/repo \
  /mnt/cache/vault/little-orbit/android-signing/little-orbit-signer.tar.age \
  /mnt/cache/little-orbit-secrets/android-signing-age-identity.txt
```

This mode builds only the signer image, decrypts beneath `/dev/shm`, verifies both password files,
the private-key entry, and the certificate against the policy-pinned fingerprint, then removes the
plaintext through the same exit trap. The verifier emits only the public certificate fingerprint.
Run it twice as independent restore checks before retiring a recovery copy.

Disposable end-to-end drills use a clean committed checkout named
`/mnt/cache/little-orbit-deploy/android-signing-drills/little-orbit-<run-id>`, a unique encrypted
throwaway signer bundle, and unique empty release-work directories. The launcher accepts exactly
that one-level drill root in addition to the production checkout; it does not broaden the
production source path. Patch the disposable policy to its throwaway certificate and use distinct
unpublished version codes. Never pass the production signer bundle to a disposable drill.

The 2026-09-26 `.14` rehearsal completed disposable Little Orbit phone/Wear and Big Orbit signing,
independent package/version/Wear-feature inspection, wrong store password, key password, alias,
and certificate rejection, secret redaction, production-bundle immutability, and zero-residue
cleanup without signing a production APK. Docker container creation wedged after an unrelated
concurrent build during the final negative matrix, so those verifier-only cases used the exact
OpenJDK 17 runtime and compiled
verifier class from each captured signer's read-only image layer; the full end-to-end signing runs
used the hardened network-disabled containers. Exact image IDs, artifact hashes, and the bounded
caveat are recorded in the
[`2026-09-26 Unraid verification record`](../operations/VERIFICATION-UNRAID-2026-09-26.md).

The runner decrypts only into `/dev/shm/little-orbit-signing/little-orbit.<run-id>`, supplies passwords to
`apksigner` through mounted files, and deletes that tmpfs directory on success, failure, or signal.
It refuses a dirty checkout or non-empty output directory. The signed output includes separate
phone and Wear hashes, byte counts, version codes, and the compatible `release-manifest.json`.
The Wear APK must independently declare `android.hardware.type.watch`; a package that omits that
required feature is rejected before a release manifest is created.

Inspect and physically cold-launch the exact signed candidates before using
`infra/scripts/publish-signed-android.ps1`. Publication stays a separate explicit action. Never
rebuild or replace an already published APK; a failed candidate requires a higher version code.
