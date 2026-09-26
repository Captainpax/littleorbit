package com.littleorbit.data;

import static org.junit.Assert.assertEquals;
import static org.junit.Assert.assertFalse;
import static org.junit.Assert.assertTrue;

import org.junit.Test;

/** Verifies relationship identity changes and purge-generation ordering. */
public final class RelationshipDisplayIdentityTest {
    @Test
    public void serverRelationshipIdentityIsCanonicalized() {
        String upper = RelationshipDisplayIdentity.canonicalId(
                "AEB31136-E199-4CC5-90AE-A5D07ED22DF4");
        String lower = RelationshipDisplayIdentity.canonicalId(
                "aeb31136-e199-4cc5-90ae-a5d07ed22df4");

        assertEquals(lower, upper);
        assertEquals(36, upper.length());
    }

    @Test
    public void purgeBlocksOldGenerationAndNewRelationshipAdvancesAgain() {
        RelationshipDisplayIdentity.Snapshot empty =
                new RelationshipDisplayIdentity.Snapshot("", 0, false, 0);
        RelationshipDisplayIdentity.Snapshot first = RelationshipDisplayIdentity.activated(
                empty, "first", 10);
        RelationshipDisplayIdentity.Snapshot same = RelationshipDisplayIdentity.activated(
                first, "first", 20);
        RelationshipDisplayIdentity.Snapshot purge =
                RelationshipDisplayIdentity.purged(same, 30);
        RelationshipDisplayIdentity.Snapshot second = RelationshipDisplayIdentity.activated(
                purge, "second", 40);

        assertEquals(first, same);
        assertEquals(10, first.generation());
        assertFalse(purge.active());
        assertTrue(purge.generation() > first.generation());
        assertTrue(second.active());
        assertTrue(second.generation() > purge.generation());
    }

    @Test
    public void aFreshInstallUsesTimeAsItsOrderingFloor() {
        RelationshipDisplayIdentity.Snapshot empty =
                new RelationshipDisplayIdentity.Snapshot("", 0, false, 0);

        RelationshipDisplayIdentity.Snapshot active = RelationshipDisplayIdentity.activated(
                empty, "relationship", 2_000_000_000_000L);

        assertEquals(2_000_000_000_000L, active.generation());
    }
}
