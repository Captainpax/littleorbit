package com.littleorbit.mobile;

import com.littleorbit.data.remote.CountdownApiModels;
import java.time.Duration;
import java.time.Instant;
import java.time.LocalDate;
import java.time.ZoneId;

/** Pure countdown calendar calculations shared by rendering and boundary tests. */
final class CountdownPresentation {
    record Remaining(long days, long hours, long minutes, boolean elapsed) {}

    private CountdownPresentation() {}

    /** Returns whole display units without double spaces or negative values. */
    static Remaining remaining(Instant event, Instant now) {
        if (!event.isAfter(now)) return new Remaining(0, 0, 0, true);
        long seconds = Duration.between(now, event).getSeconds();
        long totalMinutes = Math.max(1, (seconds + 59) / 60);
        long days = totalMinutes / (24 * 60);
        long hours = (totalMinutes % (24 * 60)) / 60;
        long minutes = totalMinutes % 60;
        return new Remaining(days, hours, minutes, false);
    }

    /** Classifies all-day events in their declared IANA timezone. */
    static boolean isPast(CountdownApiModels.Countdown value, Instant now) {
        if ("all_day".equals(value.timingKind) && value.occursOn != null) {
            ZoneId zone = safeZone(value.timezone);
            return LocalDate.parse(value.occursOn).isBefore(now.atZone(zone).toLocalDate());
        }
        return !Instant.parse(value.occursAt).isAfter(now);
    }

    private static ZoneId safeZone(String value) {
        try {
            return ZoneId.of(value);
        } catch (RuntimeException invalid) {
            return ZoneId.systemDefault();
        }
    }
}
