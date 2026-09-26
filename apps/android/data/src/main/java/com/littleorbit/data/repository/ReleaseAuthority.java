package com.littleorbit.data.repository;

import com.littleorbit.data.remote.ApiModels;
import java.net.URI;

/** Validates the two signed-release authorities trusted by the Android client. */
final class ReleaseAuthority {
    private static final String FIRST_PARTY_HOST = "lil-orb.pax-kun.com";
    private static final String GITHUB_HOST = "github.com";

    private ReleaseAuthority() {}

    /** Rejects metadata outside the matching API endpoint or historical GitHub release. */
    static void validate(ApiModels.ApkRelease release) {
        URI apk = URI.create(release.apkUrl);
        URI page = URI.create(release.githubReleaseUrl);
        String tag = "v" + release.version;
        boolean validApk = firstPartyApk(apk, release.version) || githubApk(apk, tag);
        boolean validPage = canonicalHttps(page, GITHUB_HOST)
                && page.getPath().equals("/Captainpax/littleorbit/releases/tag/" + tag);
        if (!validApk || !validPage
                || !NetworkReleaseRepository.EXPECTED_PACKAGE.equals(release.packageName)
                || !NetworkReleaseRepository.EXPECTED_SIGNER.equals(release.signerSha256)) {
            throw new NetworkReleaseRepository.ReleaseCheckException("release_metadata_invalid");
        }
    }

    private static boolean firstPartyApk(URI uri, String version) {
        return canonicalHttps(uri, FIRST_PARTY_HOST)
                && uri.getPath().equals("/api/v1/releases/" + version + "/apk");
    }

    private static boolean githubApk(URI uri, String tag) {
        String prefix = "/Captainpax/littleorbit/releases/download/" + tag + "/";
        return canonicalHttps(uri, GITHUB_HOST)
                && uri.getPath().startsWith(prefix)
                && uri.getPath().endsWith(".apk");
    }

    private static boolean canonicalHttps(URI uri, String host) {
        return "https".equals(uri.getScheme())
                && host.equals(uri.getHost())
                && (uri.getPort() == -1 || uri.getPort() == 443)
                && uri.getRawQuery() == null
                && uri.getRawFragment() == null
                && uri.getUserInfo() == null;
    }
}
