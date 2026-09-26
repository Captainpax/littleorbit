package com.littleorbit.data.local;

import androidx.annotation.NonNull;
import androidx.room.Entity;
import androidx.room.PrimaryKey;

/** Keystore-encrypted countdown snapshot used for offline viewing. */
@Entity(tableName = "countdown_cache")
public final class CountdownCacheEntity {
    @PrimaryKey @NonNull public final String countdownId;
    @NonNull public final String encryptedPayload;
    public final long occursAtEpochMillis;
    public final boolean pendingSync;
    public final boolean syncConflict;

    /** Creates one encrypted cache row without exposing its private text to Room. */
    public CountdownCacheEntity(
            @NonNull String countdownId,
            @NonNull String encryptedPayload,
            long occursAtEpochMillis,
            boolean pendingSync,
            boolean syncConflict) {
        this.countdownId = countdownId;
        this.encryptedPayload = encryptedPayload;
        this.occursAtEpochMillis = occursAtEpochMillis;
        this.pendingSync = pendingSync;
        this.syncConflict = syncConflict;
    }
}
