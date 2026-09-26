package com.littleorbit.data;

import static org.junit.Assert.assertFalse;
import static org.junit.Assert.assertTrue;

import org.junit.Test;

/** Verifies that cache purge requires authorization loss or the exact inactive code. */
public final class DisplayCacheSynchronizerTest {
    @Test
    public void ordinaryConflictDoesNotInvalidateRelationshipCache() {
        assertFalse(DisplayCacheSynchronizer.shouldInvalidateRelationship(409, false));
        assertTrue(DisplayCacheSynchronizer.shouldInvalidateRelationship(409, true));
    }

    @Test
    public void authenticationFailuresStillInvalidateRelationshipCache() {
        assertTrue(DisplayCacheSynchronizer.shouldInvalidateRelationship(401, false));
        assertTrue(DisplayCacheSynchronizer.shouldInvalidateRelationship(403, false));
        assertFalse(DisplayCacheSynchronizer.shouldInvalidateRelationship(500, false));
    }
}
