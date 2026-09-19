package com.littleorbit.mobile;

/** Immutable self-hosted Wear APK authority used by the in-app installer. */
public record WearReleaseMetadata(
        String version,
        int versionCode,
        String apkUrl,
        String sha256,
        long sizeBytes,
        String packageName,
        String signerSha256,
        int minimumAndroid,
        boolean productionAuthority) {
    public WearReleaseMetadata(
            String version,
            int versionCode,
            String apkUrl,
            String sha256,
            long sizeBytes,
            String packageName,
            String signerSha256,
            int minimumAndroid) {
        this(version, versionCode, apkUrl, sha256, sizeBytes, packageName,
                signerSha256, minimumAndroid, true);
    }
}
