package com.littleorbit.domain;

import java.time.Duration;
import java.time.Instant;
import java.util.Objects;

/** Minimal immutable together-time value safe for phone, widget, and watch displays. */
public record TogetherSnapshot(Duration estimatedDuration, Instant updatedAt) {
    /** Creates a validated snapshot. */
    public TogetherSnapshot {
        Objects.requireNonNull(estimatedDuration, "estimatedDuration");
        Objects.requireNonNull(updatedAt, "updatedAt");
        if (estimatedDuration.isNegative()) {
            throw new IllegalArgumentException("estimatedDuration must not be negative");
        }
    }

    /** Returns whether the cached value is older than the supplied tolerance. */
    public boolean isStale(Instant now, Duration tolerance) {
        Objects.requireNonNull(now, "now");
        Objects.requireNonNull(tolerance, "tolerance");
        return updatedAt.plus(tolerance).isBefore(now);
    }

    /** Returns whole estimated days for compact surfaces. */
    public long wholeDays() {
        return estimatedDuration.toDays();
    }
}
