package com.littleorbit.mobile;

import static org.junit.Assert.assertEquals;
import static org.junit.Assert.assertFalse;
import static org.junit.Assert.assertTrue;

import com.littleorbit.data.local.DisplayCacheEntity;
import java.time.Instant;
import java.time.ZoneOffset;
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
    public void failedRefreshCannotResurrectAnInvalidSession() {
        HomeScreenState staleSignedIn = HomeScreenState.signedInWithoutCache();

        HomeScreenState state = HomeStateMapper.afterRefreshFailure(staleSignedIn, false);

        assertFalse(state.signedIn());
        assertEquals("Sign in to sync", state.freshness());
    }

    @Test
    public void failedRefreshPreservesAuthorizedOfflineCache() {
        Instant now = Instant.parse("2026-09-11T12:00:00Z");
        DisplayCacheEntity cache = new DisplayCacheEntity(
                "primary", 20_000, 3_600, now.toEpochMilli(),
                "Dinner", 0, now.toEpochMilli());
        HomeScreenState cached = HomeStateMapper.fromCache(cache, true, now);

        assertEquals(cached, HomeStateMapper.afterRefreshFailure(cached, true));
    }

    @Test
    public void cacheBecomesStaleOnlyAfterFreshnessWindow() {
        Instant updatedAt = Instant.parse("2026-09-11T12:00:00Z");
        DisplayCacheEntity cache = new DisplayCacheEntity(
                "primary",
                updatedAt.atZone(ZoneOffset.UTC).toLocalDate().minusDays(2).toEpochDay(),
                172_800,
                updatedAt.toEpochMilli(),
                "Dinner",
                0,
                updatedAt.toEpochMilli());

        HomeScreenState fresh = HomeStateMapper.fromCache(
                cache, true, updatedAt.plusSeconds(6 * 60 * 60));
        HomeScreenState stale = HomeStateMapper.fromCache(
                cache, true, updatedAt.plusSeconds(6 * 60 * 60 + 1));

        assertEquals("Updated recently", fresh.freshness());
        assertEquals("Cached data may be stale", stale.freshness());
        assertEquals("2 days together", fresh.togetherTime());
        assertEquals("2d 0h nearby · estimate", fresh.nearbyTime());
    }
}
