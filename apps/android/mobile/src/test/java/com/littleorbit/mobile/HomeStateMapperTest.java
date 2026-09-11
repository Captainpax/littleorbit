package com.littleorbit.mobile;

import static org.junit.Assert.assertEquals;
import static org.junit.Assert.assertFalse;
import static org.junit.Assert.assertTrue;

import com.littleorbit.data.local.DisplayCacheEntity;
import java.time.Instant;
import org.junit.Test;

/** Regression coverage for authentication and display-cache state mapping. */
public final class HomeStateMapperTest {
    @Test
    public void signedInAccountWithoutCoupleCacheRemainsSignedIn() {
        HomeScreenState state = HomeStateMapper.withoutCache(true);

        assertTrue(state.signedIn());
        assertEquals("Not connected", state.togetherTime());
        assertEquals("Signed in — connect or retry sync", state.freshness());
    }

    @Test
    public void guestWithoutCacheRemainsSignedOut() {
        assertFalse(HomeStateMapper.withoutCache(false).signedIn());
    }

    @Test
    public void cacheBecomesStaleOnlyAfterFreshnessWindow() {
        Instant updatedAt = Instant.parse("2026-09-11T12:00:00Z");
        DisplayCacheEntity cache = new DisplayCacheEntity(
                "primary", 172_800, "Dinner", 0, updatedAt.toEpochMilli());

        HomeScreenState fresh = HomeStateMapper.fromCache(
                cache, true, updatedAt.plusSeconds(6 * 60 * 60));
        HomeScreenState stale = HomeStateMapper.fromCache(
                cache, true, updatedAt.plusSeconds(6 * 60 * 60 + 1));

        assertEquals("Updated recently", fresh.freshness());
        assertEquals("Estimate may be stale", stale.freshness());
    }
}
