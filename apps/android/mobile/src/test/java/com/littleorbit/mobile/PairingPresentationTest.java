package com.littleorbit.mobile;

import static org.junit.Assert.assertEquals;

import java.time.Instant;
import org.junit.Test;

/** Boundary tests for pasted pair codes and their ten-minute expiry display. */
public final class PairingPresentationTest {
    @Test
    public void normalizesPastedCodeSeparatorsAndCase() {
        assertEquals("AB12CD34", PairingPresentation.normalizeCode(" ab-12 cd.34 "));
    }

    @Test
    public void partialFinalSecondRemainsUsable() {
        Instant now = Instant.parse("2026-09-14T12:00:00Z");
        Instant expiry = now.plusMillis(250);

        assertEquals(1, PairingPresentation.secondsRemaining(expiry, now));
    }

    @Test
    public void expiredValuesClampAndFormatSafely() {
        Instant now = Instant.parse("2026-09-14T12:00:00Z");

        assertEquals(0, PairingPresentation.secondsRemaining(now.minusSeconds(1), now));
        assertEquals("0:00", PairingPresentation.clock(-1));
        assertEquals("10:00", PairingPresentation.clock(600));
    }
}
