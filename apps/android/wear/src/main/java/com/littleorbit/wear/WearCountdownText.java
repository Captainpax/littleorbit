package com.littleorbit.wear;

import android.content.Context;
import java.time.Duration;
import java.time.Instant;
import java.time.LocalDate;
import java.time.ZoneId;
import java.time.format.DateTimeFormatter;
import java.time.temporal.ChronoUnit;
import java.util.Locale;

/** Exact all-day/timed countdown presentation derived only from the authorized cache. */
final class WearCountdownText {
    private WearCountdownText() {}

    static String title(Context context, WearDisplayCache.State state) {
        if (!WearConfiguration.read(context).showCountdownTitles()) {
            return context.getString(R.string.next_countdown);
        }
        return state.countdownTitle == null || state.countdownTitle.isBlank()
                ? context.getString(R.string.no_countdown) : state.countdownTitle;
    }

    static String remaining(Context context, WearDisplayCache.State state, Instant now) {
        if (!state.available()) return context.getString(R.string.open_phone_to_sync);
        if ("all_day".equals(state.countdownTimingKind)) {
            try {
                ZoneId zone = ZoneId.of(state.countdownTimezone);
                LocalDate date = LocalDate.parse(state.countdownOccursOn);
                long days = ChronoUnit.DAYS.between(now.atZone(zone).toLocalDate(), date);
                if (days < 0) return context.getString(R.string.countdown_arrived);
                return context.getResources().getQuantityString(
                        R.plurals.countdown_days, (int) days, days);
            } catch (Exception invalid) {
                return context.getString(R.string.open_phone_to_sync);
            }
        }
        if (state.countdownAt <= 0) return context.getString(R.string.no_countdown);
        Duration value = Duration.between(now, Instant.ofEpochMilli(state.countdownAt));
        if (value.isNegative() || value.isZero()) return context.getString(R.string.countdown_arrived);
        long days = value.toDays();
        if (days > 0) return context.getResources().getQuantityString(
                R.plurals.countdown_days, (int) days, days);
        return context.getString(R.string.countdown_hours_minutes,
                value.toHours(), value.toMinutes() % 60);
    }

    static String when(Context context, WearDisplayCache.State state) {
        try {
            ZoneId zone = ZoneId.of(state.countdownTimezone);
            if ("all_day".equals(state.countdownTimingKind)) {
                LocalDate date = LocalDate.parse(state.countdownOccursOn);
                return date.format(DateTimeFormatter.ofPattern("EEE, MMM d", Locale.getDefault()));
            }
            return Instant.ofEpochMilli(state.countdownAt).atZone(zone)
                    .format(DateTimeFormatter.ofPattern("EEE, MMM d · h:mm a", Locale.getDefault()));
        } catch (Exception invalid) {
            return context.getString(R.string.unavailable);
        }
    }
}
