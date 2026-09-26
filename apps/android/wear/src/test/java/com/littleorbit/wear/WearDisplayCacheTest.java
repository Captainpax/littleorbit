package com.littleorbit.wear;

import static org.junit.Assert.assertEquals;
import static org.junit.Assert.assertFalse;
import static org.junit.Assert.assertTrue;

import java.time.Instant;
import java.time.LocalDate;
import org.junit.Test;

/** Pure value and stale-state tests shared by all Wear surfaces. */
public final class WearDisplayCacheTest {
    @Test
    public void rendersRelationshipAndNearbyAsSeparateValues() {
        LocalDate today = LocalDate.of(2026, 9, 12);
        WearDisplayCache.State state = new WearDisplayCache.State(
                today.minusDays(42).toEpochDay(),
                9_000,
                Instant.parse("2026-09-12T11:00:00Z").toEpochMilli(),
                "Dinner",
                0,
                Instant.parse("2026-09-12T12:00:00Z").toEpochMilli());

        assertEquals(42, state.relationshipDays(today));
        assertEquals(2, state.nearbyHours());
        assertEquals(30, state.nearbyMinutesRemainder());
        assertFalse(state.stale(Instant.parse("2026-09-12T18:00:00Z")));
        assertTrue(state.stale(Instant.parse("2026-09-12T18:00:01Z")));
    }

    @Test
    public void missingPairDateIsHonest() {
        long synced = Instant.parse("2026-09-12T12:00:00Z").toEpochMilli();
        WearDisplayCache.State state = new WearDisplayCache.State(-1, 0, 0, "None", 0, synced);

        assertEquals(-1, state.relationshipDays(LocalDate.of(2026, 9, 12)));
        assertTrue(state.stale(Instant.parse("2026-09-12T18:00:01Z")));
    }

    @Test
    public void unavailableStateNeverClaimsZeroNearbyTime() {
        WearDisplayCache.State state = WearDisplayCache.State.unavailable();

        assertFalse(state.available());
        assertEquals(-1, state.relationshipDays(LocalDate.of(2026, 9, 12)));
        assertEquals(0, state.nearbyHours());
        assertEquals(0, state.nearbyMinutesRemainder());
    }

    @Test
    public void negativeNearbyValueIsClampedBeforePresentation() {
        WearDisplayCache.State state = new WearDisplayCache.State(
                0,
                -1,
                0,
                "",
                0,
                Instant.parse("2026-09-12T12:00:00Z").toEpochMilli());

        assertEquals(0, state.nearbyHours());
        assertEquals(0, state.nearbyMinutesRemainder());
    }
}
