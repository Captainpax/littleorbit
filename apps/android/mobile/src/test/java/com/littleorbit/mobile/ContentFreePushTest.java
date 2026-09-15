package com.littleorbit.mobile;

import static org.junit.Assert.assertFalse;
import static org.junit.Assert.assertTrue;

import java.util.Map;
import org.junit.Test;

public final class ContentFreePushTest {
    @Test
    public void acceptsOnlyTheOpaqueAvailabilitySignal() {
        assertTrue(ContentFreePush.isWake(
                Map.of("signal", "notification.available"), false));
        assertFalse(ContentFreePush.isWake(
                Map.of("signal", "notification.available"), true));
        assertFalse(ContentFreePush.isWake(
                Map.of("signal", "notification.available", "name", "Partner"), false));
        assertFalse(ContentFreePush.isWake(Map.of("signal", "smooch_received"), false));
    }
}
