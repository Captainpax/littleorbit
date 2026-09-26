package com.littleorbit.domain;

import java.time.Duration;
import java.time.Instant;
import java.time.ZoneId;
import java.util.Objects;
import java.util.UUID;

/** Immutable shared countdown with an explicit display timezone. */
public record Countdown(UUID id, String title, Instant target, ZoneId timeZone, String notes, long revision) {
    /** Creates a validated countdown. */
    public Countdown {
        Objects.requireNonNull(id, "id");
        Objects.requireNonNull(title, "title");
        Objects.requireNonNull(target, "target");
        Objects.requireNonNull(timeZone, "timeZone");
        Objects.requireNonNull(notes, "notes");
        if (title.isBlank() || title.length() > 120 || notes.length() > 2_000 || revision < 0) {
            throw new IllegalArgumentException("countdown fields are outside protocol limits");
        }
    }

    /** Returns zero after the target rather than a negative display duration. */
    public Duration remainingAt(Instant now) {
        Duration remaining = Duration.between(now, target);
        return remaining.isNegative() ? Duration.ZERO : remaining;
    }
}
