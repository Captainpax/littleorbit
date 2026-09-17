package com.littleorbit.mobile;

import static org.junit.Assert.assertEquals;

import com.littleorbit.data.remote.TogetherTimeModels;
import org.junit.Test;

/** Regression tests for the bounded monotonic nearby-time presentation. */
public final class TogetherTimeProjectionTest {
    @Test
    public void nearbyProjectionAdvancesOnlyToServerDeadline() {
        TogetherTimeProjection projection = TogetherTimeProjection.from(
                summary("nearby", "2026-09-16T12:00:00Z", "2026-09-16T12:00:05Z", 40),
                10_000);

        assertEquals(40, projection.valueAt(9_000));
        assertEquals(43, projection.valueAt(13_999));
        assertEquals(45, projection.valueAt(60_000));
    }

    @Test
    public void nonNearbySnapshotNeverTicks() {
        TogetherTimeProjection projection = TogetherTimeProjection.from(
                summary("apart", "2026-09-16T12:00:00Z", "2026-09-16T12:05:00Z", 90),
                2_000);

        assertEquals(90, projection.valueAt(302_000));
    }

    @Test
    public void malformedDeadlineFailsClosed() {
        TogetherTimeProjection projection = TogetherTimeProjection.from(
                summary("nearby", "bad", "also-bad", 15), 0);

        assertEquals(15, projection.valueAt(60_000));
    }

    private static TogetherTimeModels.PairSummary summary(
            String state, String serverNow, String liveUntil, long seconds) {
        return new TogetherTimeModels.PairSummary(
                "aeb31136-e199-4cc5-90ae-a5d07ed22df4",
                "2026-09-01T18:30:00Z",
                10,
                seconds,
                seconds,
                0,
                serverNow,
                state,
                null,
                liveUntil,
                "2026-09-16T12:00:00Z",
                "high",
                3,
                false,
                100,
                true,
                true,
                "estimate");
    }
}
