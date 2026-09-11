package com.littleorbit.data.local;

import androidx.annotation.NonNull;
import androidx.room.Entity;
import androidx.room.PrimaryKey;

/** Minimal non-sensitive cache shared with widget and Wear synchronization. */
@Entity(tableName = "display_cache")
public final class DisplayCacheEntity {
    /** Singleton cache row key. */
    @PrimaryKey @NonNull public final String cacheKey;
    public final long togetherSeconds;
    public final String nextCountdownTitle;
    public final long nextCountdownEpochMillis;
    public final long updatedAtEpochMillis;

    /** Creates an immutable Room cache row with no notes, answers, locations, or tokens. */
    public DisplayCacheEntity(
            @NonNull String cacheKey,
            long togetherSeconds,
            @NonNull String nextCountdownTitle,
            long nextCountdownEpochMillis,
            long updatedAtEpochMillis) {
        this.cacheKey = cacheKey;
        this.togetherSeconds = Math.max(0, togetherSeconds);
        this.nextCountdownTitle = nextCountdownTitle;
        this.nextCountdownEpochMillis = nextCountdownEpochMillis;
        this.updatedAtEpochMillis = updatedAtEpochMillis;
    }
}
