package com.littleorbit.wear;

import android.content.Context;
import android.content.SharedPreferences;
import java.time.Duration;
import java.time.Instant;
import java.time.LocalDate;
import java.time.ZoneOffset;

/** Private, minimal cache used by the watch app, tile, and complication. */
final class WearDisplayCache {
    private static final String PREFERENCES = "little_orbit_display_v2";
    private static final Duration STALE_AFTER = Duration.ofHours(6);

    private WearDisplayCache() {}

    static void storeV2(
            Context context,
            long relationshipStartEpochDay,
            long nearbySeconds,
            long nearbyProcessedAt,
            String countdownTitle,
            long countdownAt,
            long syncedAt) {
        preferences(context).edit()
                .putLong("relationship_start_epoch_day", relationshipStartEpochDay)
                .putLong("nearby_seconds", Math.max(0, nearbySeconds))
                .putLong("nearby_processed_at", nearbyProcessedAt)
                .putString("countdown_title", countdownTitle)
                .putLong("countdown_at", countdownAt)
                .putLong("synced_at", syncedAt)
                .apply();
    }

    static void storeLegacy(
            Context context,
            long relationshipSeconds,
            String countdownTitle,
            long countdownAt,
            long updatedAt) {
        long days = Duration.ofSeconds(Math.max(0, relationshipSeconds)).toDays();
        storeV2(
                context,
                LocalDate.now(ZoneOffset.UTC).minusDays(days).toEpochDay(),
                0,
                0,
                countdownTitle,
                countdownAt,
                updatedAt);
    }

    static State read(Context context) {
        SharedPreferences values = preferences(context);
        return new State(
                values.getLong("relationship_start_epoch_day", -1),
                values.getLong("nearby_seconds", 0),
                values.getLong("nearby_processed_at", 0),
                values.getString("countdown_title", "No countdown yet"),
                values.getLong("countdown_at", 0),
                values.getLong("synced_at", 0));
    }

    private static SharedPreferences preferences(Context context) {
        return context.getSharedPreferences(PREFERENCES, Context.MODE_PRIVATE);
    }

    /** Immutable display state with conservative stale handling. */
    static final class State {
        final long relationshipStartEpochDay;
        final long nearbySeconds;
        final long nearbyProcessedAt;
        final String countdownTitle;
        final long countdownAt;
        final long syncedAt;

        State(
                long relationshipStartEpochDay,
                long nearbySeconds,
                long nearbyProcessedAt,
                String countdownTitle,
                long countdownAt,
                long syncedAt) {
            this.relationshipStartEpochDay = relationshipStartEpochDay;
            this.nearbySeconds = nearbySeconds;
            this.nearbyProcessedAt = nearbyProcessedAt;
            this.countdownTitle = countdownTitle;
            this.countdownAt = countdownAt;
            this.syncedAt = syncedAt;
        }

        boolean available() {
            return syncedAt > 0;
        }

        boolean stale() {
            return stale(Instant.now());
        }

        boolean stale(Instant now) {
            return !available()
                    || Instant.ofEpochMilli(syncedAt).plus(STALE_AFTER).isBefore(now);
        }

        String relationshipText() {
            return relationshipText(LocalDate.now(ZoneOffset.UTC));
        }

        String relationshipText(LocalDate today) {
            return relationshipStartEpochDay < 0
                    ? "Start date unset"
                    : Math.max(0, today.toEpochDay() - relationshipStartEpochDay) + " days";
        }

        String relationshipShort() {
            return relationshipStartEpochDay < 0
                    ? "—"
                    : Math.max(
                            0,
                            LocalDate.now(ZoneOffset.UTC).toEpochDay()
                                    - relationshipStartEpochDay)
                            + "d";
        }

        String nearbyText() {
            return nearbySeconds / 3_600
                    + "h "
                    + (nearbySeconds % 3_600) / 60
                    + "m nearby";
        }

        String statusText() {
            return stale() ? "Stale · open phone" : countdownTitle;
        }

        String accessibilityText() {
            return relationshipText() + " together, " + nearbyText() + ", " + statusText();
        }
    }
}
