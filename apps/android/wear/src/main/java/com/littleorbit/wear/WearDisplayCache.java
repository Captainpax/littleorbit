package com.littleorbit.wear;

import android.annotation.SuppressLint;
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
            String countdownTimingKind,
            String countdownOccursOn,
            String countdownTimezone,
            long syncedAt) {
        preferences(context).edit()
                .putLong("relationship_start_epoch_day", relationshipStartEpochDay)
                .putLong("nearby_seconds", Math.max(0, nearbySeconds))
                .putLong("nearby_processed_at", nearbyProcessedAt)
                .putString("countdown_title", countdownTitle)
                .putLong("countdown_at", countdownAt)
                .putString("countdown_timing_kind", countdownTimingKind)
                .putString("countdown_occurs_on", countdownOccursOn)
                .putString("countdown_timezone", countdownTimezone)
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
                "timed",
                "",
                "UTC",
                updatedAt);
    }

    static State read(Context context) {
        SharedPreferences values = preferences(context);
        long syncedAt = values.getLong("synced_at", 0);
        if (!WearRelationshipGuard.ensureReadable(
                context, syncedAt, System.currentTimeMillis())) return State.unavailable();
        values = preferences(context);
        return new State(
                values.getLong("relationship_start_epoch_day", -1),
                values.getLong("nearby_seconds", 0),
                values.getLong("nearby_processed_at", 0),
                values.getString("countdown_title", ""),
                values.getLong("countdown_at", 0),
                values.getString("countdown_timing_kind", "timed"),
                values.getString("countdown_occurs_on", ""),
                values.getString("countdown_timezone", "UTC"),
                values.getLong("synced_at", 0));
    }

    @SuppressLint("ApplySharedPref")
    static void clearValues(Context context) {
        // Purge callers must observe deletion before accepting another relationship record.
        preferences(context).edit().clear().commit();
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
        final String countdownTimingKind;
        final String countdownOccursOn;
        final String countdownTimezone;
        final long syncedAt;

        State(
                long relationshipStartEpochDay,
                long nearbySeconds,
                long nearbyProcessedAt,
                String countdownTitle,
                long countdownAt,
                String countdownTimingKind,
                String countdownOccursOn,
                String countdownTimezone,
                long syncedAt) {
            this.relationshipStartEpochDay = relationshipStartEpochDay;
            this.nearbySeconds = nearbySeconds;
            this.nearbyProcessedAt = nearbyProcessedAt;
            this.countdownTitle = countdownTitle;
            this.countdownAt = countdownAt;
            this.countdownTimingKind = countdownTimingKind;
            this.countdownOccursOn = countdownOccursOn;
            this.countdownTimezone = countdownTimezone;
            this.syncedAt = syncedAt;
        }

        State(
                long relationshipStartEpochDay,
                long nearbySeconds,
                long nearbyProcessedAt,
                String countdownTitle,
                long countdownAt,
                long syncedAt) {
            this(relationshipStartEpochDay, nearbySeconds, nearbyProcessedAt,
                    countdownTitle, countdownAt, "timed", "", "UTC", syncedAt);
        }

        static State unavailable() {
            return new State(-1, 0, 0, "", 0, "timed", "", "UTC", 0);
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

        long relationshipDays(LocalDate today) {
            if (!available() || relationshipStartEpochDay < 0) return -1;
            return Math.max(0, today.toEpochDay() - relationshipStartEpochDay);
        }

        long nearbyHours() {
            return Math.max(0, nearbySeconds) / 3_600;
        }

        long nearbyMinutesRemainder() {
            return Math.max(0, nearbySeconds) % 3_600 / 60;
        }
    }
}
