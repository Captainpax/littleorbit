package com.littleorbit.data.local;

import androidx.annotation.NonNull;
import androidx.room.Entity;
import androidx.room.PrimaryKey;

/** One encrypted, retry-safe countdown mutation waiting for connectivity. */
@Entity(tableName = "queued_countdowns")
public final class QueuedCountdownEntity {
    @PrimaryKey @NonNull public final String operationId;
    @NonNull public final String kind;
    public final String countdownId;
    @NonNull public final String encryptedPayload;
    public final long createdAtEpochMillis;

    /** Creates a queue row keyed by the server idempotency operation ID. */
    public QueuedCountdownEntity(
            @NonNull String operationId,
            @NonNull String kind,
            String countdownId,
            @NonNull String encryptedPayload,
            long createdAtEpochMillis) {
        this.operationId = operationId;
        this.kind = kind;
        this.countdownId = countdownId;
        this.encryptedPayload = encryptedPayload;
        this.createdAtEpochMillis = createdAtEpochMillis;
    }
}
