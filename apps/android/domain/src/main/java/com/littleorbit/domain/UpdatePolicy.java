package com.littleorbit.domain;

import java.time.Instant;
import java.util.Objects;

/** Pure decision logic for optional, required, and incompatible update offers. */
public final class UpdatePolicy {
    private UpdatePolicy() {}

    /** Possible outcomes of evaluating the installed app against one release. */
    public enum Decision {
        CURRENT,
        OPTIONAL,
        REQUIRED,
        DEVICE_INCOMPATIBLE
    }

    /** Evaluates an offer without reading a clock, package manager, or network. */
    public static Decision evaluate(
            ReleaseUpdate release, int installedVersionCode, int androidSdk, Instant now) {
        Objects.requireNonNull(release, "release");
        Objects.requireNonNull(now, "now");
        if (installedVersionCode >= release.versionCode()) {
            return Decision.CURRENT;
        }
        if (androidSdk < release.minimumAndroid()) {
            return Decision.DEVICE_INCOMPATIBLE;
        }
        boolean floorExcludesInstalled =
                installedVersionCode < release.minimumSupportedVersionCode();
        boolean enforcementStarted = release.requiredAfter() != null
                && !now.isBefore(release.requiredAfter());
        return floorExcludesInstalled && enforcementStarted
                ? Decision.REQUIRED
                : Decision.OPTIONAL;
    }
}
