package com.littleorbit.mobile;

import static org.junit.Assert.assertFalse;
import static org.junit.Assert.assertTrue;

import org.junit.Test;

/** Verifies guest filtering and one-current-destination navigation semantics. */
public final class OrbitNavigationStateTest {
    @Test
    public void guestsOnlySeePublicNativeDestinations() {
        OrbitNavigationState state = new OrbitNavigationState(OrbitDestination.HOME, false);

        assertTrue(state.isVisible(OrbitDestination.HOME));
        assertTrue(state.isVisible(OrbitDestination.UPDATES));
        assertFalse(state.isVisible(OrbitDestination.QUIZ));
        assertFalse(state.isVisible(OrbitDestination.PRIVACY));
        assertFalse(state.isVisible(OrbitDestination.SETTINGS));
    }

    @Test
    public void signedInMembersSeeEveryDestination() {
        OrbitNavigationState state = new OrbitNavigationState(OrbitDestination.SPACE, true);

        for (OrbitDestination destination : OrbitDestination.values()) {
            assertTrue(state.isVisible(destination));
        }
    }

    @Test
    public void onlyCurrentDestinationIsSelected() {
        OrbitNavigationState state = new OrbitNavigationState(OrbitDestination.UPDATES, false);

        assertTrue(state.isSelected(OrbitDestination.UPDATES));
        assertFalse(state.isSelected(OrbitDestination.HOME));
        assertFalse(state.isSelected(OrbitDestination.SETTINGS));
    }
}
