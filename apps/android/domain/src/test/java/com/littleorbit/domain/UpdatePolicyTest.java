package com.littleorbit.domain;

import static org.junit.jupiter.api.Assertions.assertEquals;

import java.time.Instant;
import org.junit.jupiter.api.Test;

/** Regression coverage for compatibility timing and monotonic update decisions. */
public final class UpdatePolicyTest {
    private static ReleaseUpdate release(Instant requiredAfter) {
        return new ReleaseUpdate(
                "1.0.0-rc.3", 3, "https://example.test/app.apk", "https://example.test/release",
                "a".repeat(64), 100, "com.littleorbit.mobile", "b".repeat(64),
                29, 3, requiredAfter, "Notes", Instant.parse("2026-09-11T00:00:00Z"));
    }

    @Test
    public void newerReleaseIsOptionalBeforeExplicitEnforcement() {
        assertEquals(
                UpdatePolicy.Decision.OPTIONAL,
                UpdatePolicy.evaluate(
                        release(Instant.parse("2026-10-01T00:00:00Z")),
                        2,
                        36,
                        Instant.parse("2026-09-30T23:59:59Z")));
    }

    @Test
    public void compatibilityFloorBecomesRequiredAtItsUtcInstant() {
        Instant enforcement = Instant.parse("2026-10-01T00:00:00Z");
        assertEquals(
                UpdatePolicy.Decision.REQUIRED,
                UpdatePolicy.evaluate(release(enforcement), 2, 36, enforcement));
    }

    @Test
    public void installedAndIncompatibleDevicesDoNotReceiveInstallOffer() {
        Instant now = Instant.parse("2026-10-01T00:00:00Z");
        assertEquals(UpdatePolicy.Decision.CURRENT, UpdatePolicy.evaluate(release(null), 3, 36, now));
        assertEquals(
                UpdatePolicy.Decision.DEVICE_INCOMPATIBLE,
                UpdatePolicy.evaluate(release(null), 2, 28, now));
    }
}
