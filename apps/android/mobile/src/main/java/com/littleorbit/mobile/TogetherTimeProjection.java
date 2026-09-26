package com.littleorbit.mobile;

import com.littleorbit.data.remote.TogetherTimeModels;
import java.time.Duration;
import java.time.Instant;

/** Monotonic, bounded presentation of one server-authorized nearby-time snapshot. */
final class TogetherTimeProjection {
    private final long serverSeconds;
    private final long receivedElapsedMillis;
    private final long maximumAdvanceSeconds;

    private TogetherTimeProjection(
            long serverSeconds, long receivedElapsedMillis, long maximumAdvanceSeconds) {
        this.serverSeconds = Math.max(0, serverSeconds);
        this.receivedElapsedMillis = receivedElapsedMillis;
        this.maximumAdvanceSeconds = Math.max(0, maximumAdvanceSeconds);
    }

    /** Anchors a response to elapsed realtime so wall-clock changes cannot add time. */
    static TogetherTimeProjection from(
            TogetherTimeModels.PairSummary summary, long receivedElapsedMillis) {
        if (!"nearby".equals(summary.countingState)
                || summary.serverNow == null || summary.countingLiveUntil == null) {
            return fixed(summary.nearbyEstimatedSeconds, receivedElapsedMillis);
        }
        try {
            long allowance = Math.max(0, Duration.between(
                    Instant.parse(summary.serverNow), Instant.parse(summary.countingLiveUntil))
                    .getSeconds());
            return new TogetherTimeProjection(
                    summary.nearbyEstimatedSeconds, receivedElapsedMillis, allowance);
        } catch (RuntimeException invalidContract) {
            return fixed(summary.nearbyEstimatedSeconds, receivedElapsedMillis);
        }
    }

    /** Returns a display value that freezes exactly at the server's evidence deadline. */
    long valueAt(long elapsedMillis) {
        long elapsedSeconds = Math.max(0, elapsedMillis - receivedElapsedMillis) / 1000;
        return serverSeconds + Math.min(elapsedSeconds, maximumAdvanceSeconds);
    }

    private static TogetherTimeProjection fixed(long seconds, long elapsedMillis) {
        return new TogetherTimeProjection(seconds, elapsedMillis, 0);
    }
}
