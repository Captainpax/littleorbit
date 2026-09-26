package com.littleorbit.mobile;

import static org.junit.Assert.assertEquals;

import org.junit.Test;

/** Regression tests for watch device, downgrade, and security-patch gates. */
public final class WearInstallPolicyTest {
    private static WearReleaseMetadata release() {
        return new WearReleaseMetadata("1.0.0-rc.8", 8, "https://example.test", "a", 1,
                "com.littleorbit.mobile", "b", 30);
    }

    @Test public void rejectsPhonesAndDowngrades() {
        assertEquals(WearInstallPolicy.Decision.REJECT_DEVICE,
                WearInstallPolicy.decide(release(), device(7, "phone", "2026-06-01")));
        assertEquals(WearInstallPolicy.Decision.REJECT_DEVICE,
                WearInstallPolicy.decide(release(), new KadbWatchClient.Device(
                        "Old watch", 29, "2026-06-01", 0, "watch")));
        assertEquals(WearInstallPolicy.Decision.REJECT_DOWNGRADE,
                WearInstallPolicy.decide(release(), device(9, "watch", "2026-06-01")));
    }

    @Test public void warnsForOldOrUnknownPatchAndAllowsCurrentPatch() {
        assertEquals(WearInstallPolicy.Decision.WARN_OLD_PATCH,
                WearInstallPolicy.decide(release(), device(0, "watch", "2026-04-05")));
        assertEquals(WearInstallPolicy.Decision.WARN_OLD_PATCH,
                WearInstallPolicy.decide(release(), device(0, "watch", "unknown")));
        assertEquals(WearInstallPolicy.Decision.WARN_OLD_PATCH,
                WearInstallPolicy.decide(release(), device(0, "watch", null)));
        assertEquals(WearInstallPolicy.Decision.INSTALL,
                WearInstallPolicy.decide(release(), device(0, "watch", "2026-05-01")));
    }

    @Test public void identifiesCurrentVersion() {
        assertEquals(WearInstallPolicy.Decision.ALREADY_CURRENT,
                WearInstallPolicy.decide(release(), device(8, "watch", "2026-06-01")));
    }

    private static KadbWatchClient.Device device(int version, String traits, String patch) {
        return new KadbWatchClient.Device("Watch", 35, patch, version, traits);
    }
}
