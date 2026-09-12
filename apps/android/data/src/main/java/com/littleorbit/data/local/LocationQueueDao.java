package com.littleorbit.data.local;

import androidx.room.Dao;
import androidx.room.Insert;
import androidx.room.OnConflictStrategy;
import androidx.room.Query;
import java.util.List;

/** Bounded encrypted location queue operations. */
@Dao
public interface LocationQueueDao {
    /** Adds one retry-safe sample without replacing a prior sample ID. */
    @Insert(onConflict = OnConflictStrategy.IGNORE)
    void insert(QueuedLocationEntity sample);

    /** Reads the oldest bounded upload batch. */
    @Query("SELECT * FROM queued_locations ORDER BY recordedAtEpochMillis LIMIT 48")
    List<QueuedLocationEntity> oldestBatch();

    /** Deletes acknowledged or policy-expired rows. */
    @Query("DELETE FROM queued_locations WHERE sampleId IN (:sampleIds)")
    void deleteByIds(List<String> sampleIds);

    /** Deletes every queued coordinate immediately when consent is withdrawn. */
    @Query("DELETE FROM queued_locations")
    void clear();

    /** Removes samples older than the server's raw-coordinate retention window. */
    @Query("DELETE FROM queued_locations WHERE recordedAtEpochMillis <= :cutoffEpochMillis")
    void deleteOlderThan(long cutoffEpochMillis);

    /** Retains at most the most recent 96 encrypted samples during long outages. */
    @Query("DELETE FROM queued_locations WHERE sampleId NOT IN ("
            + "SELECT sampleId FROM queued_locations ORDER BY recordedAtEpochMillis DESC LIMIT 96)")
    void trimToLimit();
}
