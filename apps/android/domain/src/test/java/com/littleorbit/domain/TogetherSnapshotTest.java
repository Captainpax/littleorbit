package com.littleorbit.domain;

import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.junit.jupiter.api.Assertions.assertTrue;

import java.time.Duration;
import java.time.Instant;
import org.junit.jupiter.api.Test;

class TogetherSnapshotTest {
    @Test
    void staleBoundaryIsDeterministic() {
        Instant update = Instant.parse("2026-09-10T12:00:00Z");
        TogetherSnapshot snapshot = new TogetherSnapshot(Duration.ofDays(642), update);
        assertFalse(snapshot.isStale(update.plus(Duration.ofHours(6)), Duration.ofHours(6)));
        assertTrue(snapshot.isStale(update.plus(Duration.ofHours(6).plusSeconds(1)), Duration.ofHours(6)));
    }

    @Test
    void negativeEstimateIsRejected() {
        assertThrows(IllegalArgumentException.class,
                () -> new TogetherSnapshot(Duration.ofSeconds(-1), Instant.EPOCH));
    }
}
