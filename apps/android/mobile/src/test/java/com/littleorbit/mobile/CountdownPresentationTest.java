package com.littleorbit.mobile;

import static org.junit.Assert.assertEquals;
import static org.junit.Assert.assertFalse;
import static org.junit.Assert.assertTrue;

import com.littleorbit.data.remote.CountdownApiModels;
import java.time.Instant;
import java.util.List;
import org.junit.Test;

/** Locks countdown rounding and timezone-aware all-day boundaries. */
public final class CountdownPresentationTest {
    private static final Instant NOW = Instant.parse("2026-09-14T12:00:00Z");

    @Test
    public void futurePartialMinuteRoundsUpWithoutNegativeUnits() {
        CountdownPresentation.Remaining result = CountdownPresentation.remaining(
                NOW.plusSeconds(61), NOW);

        assertEquals(0, result.days());
        assertEquals(0, result.hours());
        assertEquals(2, result.minutes());
        assertFalse(result.elapsed());
    }

    @Test
    public void exactAndPastInstantsAreElapsed() {
        assertTrue(CountdownPresentation.remaining(NOW, NOW).elapsed());
        assertTrue(CountdownPresentation.remaining(NOW.minusSeconds(1), NOW).elapsed());
    }

    @Test
    public void timedEventAtCurrentInstantMovesToHistory() {
        CountdownApiModels.Countdown value = new CountdownApiModels.Countdown(
                "id", "Now", NOW.toString(), "UTC", "", 1, NOW.toString());

        assertTrue(CountdownPresentation.isPast(value, NOW));
    }

    @Test
    public void allDayEventExpiresAfterItsDeclaredLocalDate() {
        CountdownApiModels.Countdown value = countdown(
                "2026-09-14", "America/Los_Angeles", "2026-09-14T07:00:00Z");

        assertFalse(CountdownPresentation.isPast(value,
                Instant.parse("2026-09-15T06:59:59Z")));
        assertTrue(CountdownPresentation.isPast(value,
                Instant.parse("2026-09-15T07:00:00Z")));
    }

    private static CountdownApiModels.Countdown countdown(
            String localDate, String timezone, String instant) {
        return new CountdownApiModels.Countdown(
                "id", "A day", instant, timezone, "all_day", localDate,
                List.of(), "", 1, NOW.toString(), false, false);
    }
}
