package com.littleorbit.data.local;

import androidx.annotation.NonNull;
import androidx.room.Entity;
import androidx.room.Ignore;
import androidx.room.PrimaryKey;

/** Minimal non-sensitive cache shared with widget and Wear synchronization. */
@Entity(tableName = "display_cache")
public final class DisplayCacheEntity {
    /** Singleton cache row key. */
    @PrimaryKey @NonNull public final String cacheKey;
    public final long relationshipStartEpochDay;
    public final long nearbySeconds;
    public final long nearbyProcessedAtEpochMillis;
    @NonNull public final String nextCountdownTitle;
    public final long nextCountdownEpochMillis;
    @NonNull public final String nextCountdownTimingKind;
    @NonNull public final String nextCountdownOccursOn;
    @NonNull public final String nextCountdownTimezone;
    public final long cacheSyncedAtEpochMillis;

    /** Backward-compatible constructor for callers that only need a timed countdown. */
    @Ignore
    public DisplayCacheEntity(
            @NonNull String cacheKey,
            long relationshipStartEpochDay,
            long nearbySeconds,
            long nearbyProcessedAtEpochMillis,
            @NonNull String nextCountdownTitle,
            long nextCountdownEpochMillis,
            long cacheSyncedAtEpochMillis) {
        this(cacheKey, relationshipStartEpochDay, nearbySeconds,
                nearbyProcessedAtEpochMillis, nextCountdownTitle,
                nextCountdownEpochMillis, "timed", "", "UTC",
                cacheSyncedAtEpochMillis);
    }

    /** Creates an immutable Room cache row with no notes, answers, locations, or tokens. */
    public DisplayCacheEntity(
            @NonNull String cacheKey,
            long relationshipStartEpochDay,
            long nearbySeconds,
            long nearbyProcessedAtEpochMillis,
            @NonNull String nextCountdownTitle,
            long nextCountdownEpochMillis,
            @NonNull String nextCountdownTimingKind,
            @NonNull String nextCountdownOccursOn,
            @NonNull String nextCountdownTimezone,
            long cacheSyncedAtEpochMillis) {
        this.cacheKey = cacheKey;
        this.relationshipStartEpochDay = relationshipStartEpochDay;
        this.nearbySeconds = Math.max(0, nearbySeconds);
        this.nearbyProcessedAtEpochMillis = nearbyProcessedAtEpochMillis;
        this.nextCountdownTitle = nextCountdownTitle;
        this.nextCountdownEpochMillis = nextCountdownEpochMillis;
        this.nextCountdownTimingKind = nextCountdownTimingKind;
        this.nextCountdownOccursOn = nextCountdownOccursOn;
        this.nextCountdownTimezone = nextCountdownTimezone;
        this.cacheSyncedAtEpochMillis = cacheSyncedAtEpochMillis;
    }
}
