package com.littleorbit.data.local;

import androidx.annotation.NonNull;
import androidx.room.Entity;
import androidx.room.PrimaryKey;

/** Keystore-encrypted location sample waiting for a consent-checked upload. */
@Entity(tableName = "queued_locations")
public final class QueuedLocationEntity {
    @PrimaryKey @NonNull public final String sampleId;
    @NonNull public final String encryptedPayload;
    public final long recordedAtEpochMillis;

    /** Creates an encrypted queue row; coordinates never occupy database columns. */
    public QueuedLocationEntity(
            @NonNull String sampleId,
            @NonNull String encryptedPayload,
            long recordedAtEpochMillis) {
        this.sampleId = sampleId;
        this.encryptedPayload = encryptedPayload;
        this.recordedAtEpochMillis = recordedAtEpochMillis;
    }
}
