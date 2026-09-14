package com.littleorbit.mobile;

import static org.junit.Assert.assertEquals;

import com.littleorbit.data.remote.CountdownApiModels;
import java.time.Instant;
import java.util.List;
import org.junit.Test;

/** Calendar-boundary tests for local reminder calculation. */
public final class CountdownReminderSchedulerTest {
    @Test
    public void allDayReminderUsesNineAmAfterDstTransition() {
        CountdownApiModels.Countdown value = countdown(
                "2026-11-01T07:00:00Z", "all_day", "2026-11-01");

        assertEquals(
                Instant.parse("2026-11-01T17:00:00Z"),
                CountdownReminderScheduler.reminderInstant(value));
    }

    @Test
    public void timedReminderUsesExactServerInstant() {
        CountdownApiModels.Countdown value = countdown("2026-09-25T01:00:00Z", "timed", null);

        assertEquals(
                Instant.parse("2026-09-25T01:00:00Z"),
                CountdownReminderScheduler.reminderInstant(value));
    }

    private static CountdownApiModels.Countdown countdown(
            String occursAt, String kind, String occursOn) {
        return new CountdownApiModels.Countdown(
                "id", "Cabin weekend", occursAt, "America/Los_Angeles",
                kind, occursOn, List.of(0, 60), "", 0,
                "2026-09-13T00:00:00Z", false, false);
    }
}
