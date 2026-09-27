package com.littleorbit.data;

import static org.junit.Assert.assertEquals;

import org.junit.Test;

/** Documents the selected-watch defaults that the Android store enforces. */
public final class ManagedWatchPolicyTest {
    @Test
    public void destinationsUseTogetherAsSafeFallback() {
        assertEquals("together", ManagedWatchStore.DESTINATION_TOGETHER);
        assertEquals("together", ManagedWatchStore.resolveDestination("unknown", true));
        assertEquals("countdown", ManagedWatchStore.resolveDestination("countdown", false));
        assertEquals("together", ManagedWatchStore.resolveDestination("smooch", false));
    }
}
