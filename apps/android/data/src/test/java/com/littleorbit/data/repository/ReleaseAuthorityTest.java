package com.littleorbit.data.repository;

import static org.junit.Assert.assertThrows;

import com.littleorbit.data.remote.ApiModels;
import org.junit.Test;

/** Trust-boundary tests for updater download and release-page URLs. */
public final class ReleaseAuthorityTest {
    @Test
    public void acceptsMatchingFirstPartyApk() {
        ReleaseAuthority.validate(release(
                "https://lil-orb.pax-kun.com/api/v1/releases/1.0.0-rc.4/apk"));
    }

    @Test
    public void acceptsHistoricalCanonicalGithubApk() {
        ReleaseAuthority.validate(release(
                "https://github.com/Captainpax/littleorbit/releases/download/"
                        + "v1.0.0-rc.4/little-orbit-1.0.0-rc.4.apk"));
    }

    @Test
    public void rejectsWrongFirstPartyPathOrQuery() {
        assertThrows(NetworkReleaseRepository.ReleaseCheckException.class, () -> ReleaseAuthority.validate(release(
                "https://lil-orb.pax-kun.com/api/v1/releases/1.0.0-rc.3/apk")));
        assertThrows(NetworkReleaseRepository.ReleaseCheckException.class, () -> ReleaseAuthority.validate(release(
                "https://lil-orb.pax-kun.com/api/v1/releases/1.0.0-rc.4/apk?source=x")));
    }

    @Test
    public void rejectsLookalikeHost() {
        assertThrows(NetworkReleaseRepository.ReleaseCheckException.class, () -> ReleaseAuthority.validate(release(
                "https://lil-orb.pax-kun.com.example/api/v1/releases/1.0.0-rc.4/apk")));
    }

    private static ApiModels.ApkRelease release(String apkUrl) {
        return new ApiModels.ApkRelease(
                "1.0.0-rc.4",
                4,
                apkUrl,
                "https://github.com/Captainpax/littleorbit/releases/tag/v1.0.0-rc.4",
                "a".repeat(64),
                1024,
                NetworkReleaseRepository.EXPECTED_PACKAGE,
                NetworkReleaseRepository.EXPECTED_SIGNER,
                29,
                1,
                null,
                "First-party downloads.",
                "2026-09-12T12:00:00Z");
    }
}
