package com.littleorbit.wear;

import static org.junit.Assert.assertEquals;
import static org.junit.Assert.assertFalse;
import static org.junit.Assert.assertTrue;

import org.junit.Test;

public final class WearControllerPolicyTest {
    @Test public void firstCurrentRecordBindsItsSourcePhone() {
        WearControllerPolicy.Decision result = WearControllerPolicy.decide(
                authority("", 0, ""), "watch", "watch", 4, "phone-a");

        assertTrue(result.accepted());
        assertTrue(result.clearPrivateState());
        assertEquals("phone-a", result.next().controllerNodeId());
    }

    @Test public void anotherPhoneCannotTakeOverSameGeneration() {
        WearControllerPolicy.Decision result = WearControllerPolicy.decide(
                authority("watch", 4, "phone-a"), "watch", "watch", 4, "phone-b");

        assertFalse(result.accepted());
        assertFalse(result.clearPrivateState());
        assertEquals("phone-a", result.next().controllerNodeId());
    }

    @Test public void newerNonTargetRecordPurgesWithoutBindingSender() {
        WearControllerPolicy.Decision result = WearControllerPolicy.decide(
                authority("watch", 4, "phone-a"), "watch", "other-watch", 5, "phone-b");

        assertFalse(result.accepted());
        assertTrue(result.clearPrivateState());
        assertEquals("", result.next().controllerNodeId());
        assertEquals(5, result.next().generation());
    }

    @Test public void purgeGenerationAllowsNewControllerBinding() {
        WearControllerPolicy.Decision result = WearControllerPolicy.decide(
                authority("", 5, ""), "watch", "watch", 5, "phone-b");

        assertTrue(result.accepted());
        assertEquals("phone-b", result.next().controllerNodeId());
    }

    private static WearControllerPolicy.Authority authority(
            String target, long generation, String controller) {
        return new WearControllerPolicy.Authority(target, generation, controller);
    }
}
