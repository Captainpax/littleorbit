package com.littleorbit.data.local;

import androidx.lifecycle.LiveData;
import androidx.room.Dao;
import androidx.room.Insert;
import androidx.room.OnConflictStrategy;
import androidx.room.Query;

/** Persistence operations for the singleton compact display cache. */
@Dao
public interface DisplayCacheDao {
    /** Observes cache updates for phone surfaces. */
    @Query("SELECT * FROM display_cache WHERE cacheKey = 'primary'")
    LiveData<DisplayCacheEntity> observe();

    /** Reads the cache synchronously on a bounded worker thread for widgets. */
    @Query("SELECT * FROM display_cache WHERE cacheKey = 'primary'")
    DisplayCacheEntity read();

    /** Replaces the cache atomically after a successful authorized sync. */
    @Insert(onConflict = OnConflictStrategy.REPLACE)
    void replace(DisplayCacheEntity entity);

    /** Removes relationship display data when the local account context changes. */
    @Query("DELETE FROM display_cache")
    void clear();
}
