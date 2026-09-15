package com.littleorbit.mobile;

import static org.junit.Assert.assertEquals;
import static org.junit.Assert.assertFalse;
import static org.junit.Assert.assertTrue;

import org.junit.Test;

/** Verifies Home setup progress is derived from live capabilities. */
public final class SetupChecklistStateTest {
    @Test
    public void readinessCountReflectsEveryIndependentOption() {
        SetupChecklistState state = new SetupChecklistState(
                true, true, false, true, false, false);

        assertEquals(3, state.readyCount());
        assertFalse(state.allReady());
    }

    @Test
    public void collapseDoesNotClaimOptionalCapabilitiesAreReady() {
        SetupChecklistState state = new SetupChecklistState(
                true, true, true, true, false, true);

        assertEquals(4, state.readyCount());
        assertTrue(state.allReady());
        assertTrue(state.collapsed());
    }

    @Test
    public void optionalWatchDoesNotBlockCoreSetup() {
        SetupChecklistState state = new SetupChecklistState(
                true, true, true, true, false, false);

        assertTrue(state.allReady());
    }
}
