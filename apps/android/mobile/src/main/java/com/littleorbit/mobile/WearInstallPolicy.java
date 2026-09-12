package com.littleorbit.mobile;

import java.time.LocalDate;
import java.time.format.DateTimeParseException;

/** Pure compatibility, downgrade, and May 2026 wireless-ADB warning policy. */
final class WearInstallPolicy {
    static final LocalDate SAFE_PATCH = LocalDate.of(2026, 5, 1);
    private WearInstallPolicy() {}

    enum Decision { INSTALL, WARN_OLD_PATCH, ALREADY_CURRENT, REJECT_DEVICE, REJECT_DOWNGRADE }

    static Decision decide(WearReleaseMetadata release, KadbWatchClient.Device device) {
        if (!device.isWatch() || device.sdk() < release.minimumAndroid()) return Decision.REJECT_DEVICE;
        if (device.installedVersion() == release.versionCode()) return Decision.ALREADY_CURRENT;
        if (device.installedVersion() > release.versionCode()) return Decision.REJECT_DOWNGRADE;
        try {
            if (device.securityPatch() == null
                    || LocalDate.parse(device.securityPatch()).isBefore(SAFE_PATCH)) {
                return Decision.WARN_OLD_PATCH;
            }
        } catch (DateTimeParseException invalid) { return Decision.WARN_OLD_PATCH; }
        return Decision.INSTALL;
    }
}
