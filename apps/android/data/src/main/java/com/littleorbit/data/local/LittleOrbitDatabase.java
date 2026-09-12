package com.littleorbit.data.local;

import androidx.room.Database;
import androidx.room.RoomDatabase;

/** Local database containing public display cache and encrypted sensitive queue payloads. */
@Database(
        entities = {
            DisplayCacheEntity.class,
            QueuedLocationEntity.class,
            CountdownCacheEntity.class,
            QueuedCountdownEntity.class
        },
        version = 4,
        exportSchema = true)
public abstract class LittleOrbitDatabase extends RoomDatabase {
    /** Returns display cache operations. */
    public abstract DisplayCacheDao displayCache();

    /** Returns encrypted offline location queue operations. */
    public abstract LocationQueueDao locationQueue();

    /** Returns encrypted countdown cache and queue operations. */
    public abstract CountdownDao countdowns();
}
