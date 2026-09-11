package com.littleorbit.data.local;

import androidx.room.Dao;
import androidx.room.Insert;
import androidx.room.OnConflictStrategy;
import androidx.room.Query;
import androidx.room.Transaction;
import java.util.List;

/** Encrypted countdown cache and mutation-queue operations. */
@Dao
public interface CountdownDao {
    /** Lists cached countdowns in display order. */
    @Query("SELECT * FROM countdown_cache ORDER BY occursAtEpochMillis")
    List<CountdownCacheEntity> cached();

    /** Inserts or replaces an optimistic local snapshot. */
    @Insert(onConflict = OnConflictStrategy.REPLACE)
    void upsertCache(CountdownCacheEntity item);

    /** Inserts server snapshots while preserving locally pending versions. */
    @Insert(onConflict = OnConflictStrategy.IGNORE)
    void insertRemote(List<CountdownCacheEntity> items);

    /** Removes server-confirmed rows before a cache refresh. */
    @Query("DELETE FROM countdown_cache WHERE pendingSync = 0 AND syncConflict = 0")
    void deleteSyncedCache();

    /** Replaces confirmed snapshots without overwriting queued edits. */
    @Transaction
    default void replaceRemote(List<CountdownCacheEntity> items) {
        deleteSyncedCache();
        insertRemote(items);
    }

    /** Removes a deleted or superseded local snapshot. */
    @Query("DELETE FROM countdown_cache WHERE countdownId = :countdownId")
    void deleteCache(String countdownId);

    /** Queues a retry without replacing another operation ID. */
    @Insert(onConflict = OnConflictStrategy.IGNORE)
    void enqueue(QueuedCountdownEntity item);

    /** Returns the oldest bounded mutation batch. */
    @Query("SELECT * FROM queued_countdowns ORDER BY createdAtEpochMillis LIMIT 20")
    List<QueuedCountdownEntity> queued();

    /** Removes one acknowledged operation. */
    @Query("DELETE FROM queued_countdowns WHERE operationId = :operationId")
    void deleteQueued(String operationId);

    /** Folds edits to an unsent local create into that original idempotent operation. */
    @Query("UPDATE queued_countdowns SET encryptedPayload = :encryptedPayload "
            + "WHERE operationId = :operationId AND kind = 'create'")
    void updateQueuedCreate(String operationId, String encryptedPayload);

    /** Retains the local version for explicit user reconciliation after HTTP 409. */
    @Query("UPDATE countdown_cache SET pendingSync = 0, syncConflict = 1 "
            + "WHERE countdownId = :countdownId")
    void markConflict(String countdownId);

    /** Clears private offline data when the account leaves this installation. */
    @Query("DELETE FROM queued_countdowns")
    void clearQueue();

    /** Clears private cached countdowns when the account leaves this installation. */
    @Query("DELETE FROM countdown_cache")
    void clearCache();
}
