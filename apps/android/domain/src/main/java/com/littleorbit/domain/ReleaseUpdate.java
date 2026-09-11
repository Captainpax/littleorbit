package com.littleorbit.domain;

import java.time.Instant;
import java.util.Objects;

/** Immutable server description of one signed Android application release. */
public record ReleaseUpdate(
        String version,
        int versionCode,
        String apkUrl,
        String githubReleaseUrl,
        String sha256,
        long sizeBytes,
        String packageName,
        String signerSha256,
        int minimumAndroid,
        int minimumSupportedVersionCode,
        Instant requiredAfter,
        String releaseNotes,
        Instant publishedAt) {

    /** Rejects malformed update metadata before platform download behavior can consume it. */
    public ReleaseUpdate {
        Objects.requireNonNull(version, "version");
        Objects.requireNonNull(apkUrl, "apkUrl");
        Objects.requireNonNull(githubReleaseUrl, "githubReleaseUrl");
        Objects.requireNonNull(sha256, "sha256");
        Objects.requireNonNull(packageName, "packageName");
        Objects.requireNonNull(signerSha256, "signerSha256");
        Objects.requireNonNull(releaseNotes, "releaseNotes");
        Objects.requireNonNull(publishedAt, "publishedAt");
        if (versionCode < 1 || sizeBytes < 1 || minimumAndroid < 1) {
            throw new IllegalArgumentException("Release numbers must be positive");
        }
        if (minimumSupportedVersionCode < 1 || minimumSupportedVersionCode > versionCode) {
            throw new IllegalArgumentException("Release compatibility floor is invalid");
        }
        if (!sha256.matches("[a-f0-9]{64}") || !signerSha256.matches("[a-f0-9]{64}")) {
            throw new IllegalArgumentException("Release digests must be lowercase SHA-256");
        }
    }

    /** Stable identity that changes whenever release bytes or version change. */
    public String releaseId() {
        return versionCode + ":" + sha256;
    }
}
