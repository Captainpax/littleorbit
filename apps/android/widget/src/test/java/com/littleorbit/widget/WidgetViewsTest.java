package com.littleorbit.widget;

import static org.junit.Assert.assertFalse;
import static org.junit.Assert.assertTrue;

import com.littleorbit.data.local.DisplayCacheEntity;
import java.time.Duration;
import java.time.Instant;
import org.junit.Test;

/** Regression tests for deterministic widget labels and stale boundaries. */
public final class WidgetViewsTest {
    private static final Instant NOW = Instant.parse("2026-09-12T20:00:00Z");

    @Test
    public void cacheBecomesStaleOnlyAfterSixHours() {
        assertFalse(WidgetViews.isStale(cache(NOW.minus(Duration.ofHours(6)), NOW, 0), NOW));
        assertTrue(WidgetViews.isStale(
                cache(NOW.minus(Duration.ofHours(6)).minusMillis(1), NOW, 0), NOW));
        assertFalse(WidgetViews.isStale(cache(NOW, Instant.EPOCH, 0), NOW));
        assertTrue(WidgetViews.isStale(
                cache(NOW, NOW.minus(Duration.ofHours(6)).minusMillis(1), 0), NOW));
    }

    @Test
    public void cacheExpiresAtTwentyFourHours() {
        assertFalse(WidgetViews.isExpired(
                cache(NOW.minus(Duration.ofHours(24)).plusMillis(1), NOW, 0), NOW));
        assertTrue(WidgetViews.isExpired(
                cache(NOW.minus(Duration.ofHours(24)), NOW, 0), NOW));
    }

    @Test
    public void launcherHeightSelectsACompactOrExpandedLayout() {
        assertTrue(WidgetViews.isCompact(110));
        assertFalse(WidgetViews.isCompact(180));
        assertFalse(WidgetViews.isCompact(0));
    }

    private static DisplayCacheEntity cache(
            Instant syncedAt, Instant processedAt, long relationshipStartEpochDay) {
        return new DisplayCacheEntity(
                "primary", relationshipStartEpochDay, 0, processedAt.toEpochMilli(),
                "No countdown yet", 0,
                syncedAt.toEpochMilli());
    }
}
