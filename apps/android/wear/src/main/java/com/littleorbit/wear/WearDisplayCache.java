package com.littleorbit.wear;

import android.content.Context;
import android.content.SharedPreferences;
import java.time.Duration;
import java.time.Instant;

/** Private, minimal cache used by the watch app, tile, and complication. */
final class WearDisplayCache {
    private static final String PREFERENCES = "little_orbit_display_v1";
    private static final Duration STALE_AFTER = Duration.ofHours(6);

    private WearDisplayCache() {}

    static void store(
            Context context,
            long togetherSeconds,
            String countdownTitle,
            long countdownAt,
            long updatedAt) {
        preferences(context).edit()
                .putLong("together_seconds", Math.max(0, togetherSeconds))
                .putString("countdown_title", countdownTitle)
                .putLong("countdown_at", countdownAt)
                .putLong("updated_at", updatedAt)
                .apply();
    }

    static State read(Context context) {
        SharedPreferences values = preferences(context);
        return new State(
                values.getLong("together_seconds", 0),
                values.getString("countdown_title", "No countdown yet"),
                values.getLong("countdown_at", 0),
                values.getLong("updated_at", 0));
    }

    private static SharedPreferences preferences(Context context) {
        return context.getSharedPreferences(PREFERENCES, Context.MODE_PRIVATE);
    }

    /** Immutable display state with conservative stale handling. */
    static final class State {
        final long togetherSeconds;
        final String countdownTitle;
        final long countdownAt;
        final long updatedAt;

        State(long togetherSeconds, String countdownTitle, long countdownAt, long updatedAt) {
            this.togetherSeconds = togetherSeconds;
            this.countdownTitle = countdownTitle;
            this.countdownAt = countdownAt;
            this.updatedAt = updatedAt;
        }

        boolean available() {
            return updatedAt > 0;
        }

        boolean stale() {
            return !available()
                    || Instant.ofEpochMilli(updatedAt).plus(STALE_AFTER).isBefore(Instant.now());
        }

        String togetherText() {
            return available() ? Duration.ofSeconds(togetherSeconds).toDays() + " days" : "—";
        }

        String statusText() {
            return stale() ? "Stale · open phone" : countdownTitle;
        }
    }
}
