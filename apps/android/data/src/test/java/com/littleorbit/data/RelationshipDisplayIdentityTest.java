package com.littleorbit.data;

import static org.junit.Assert.assertEquals;
import static org.junit.Assert.assertFalse;
import static org.junit.Assert.assertNotEquals;
import static org.junit.Assert.assertTrue;

import org.junit.Test;

/** Verifies relationship identity changes and purge-generation ordering. */
public final class RelationshipDisplayIdentityTest {
    @Test
    public void canonicalPairInstantProducesStableOpaqueIdentity() {
        String utc = RelationshipDisplayIdentity.relationshipId("2026-09-14T18:00:00Z");
        String offset = RelationshipDisplayIdentity.relationshipId("2026-09-14T11:00:00-07:00");

        assertEquals(utc, offset);
        assertEquals(32, utc.length());
        assertNotEquals("2026-09-14T18:00:00Z", utc);
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
