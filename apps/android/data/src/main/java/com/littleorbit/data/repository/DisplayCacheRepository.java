package com.littleorbit.data.repository;

import androidx.lifecycle.LiveData;
import com.littleorbit.data.local.DisplayCacheEntity;

/** Access boundary for the minimal phone/widget/watch display cache. */
public interface DisplayCacheRepository {
    /** Observes compact cache updates. */
    LiveData<DisplayCacheEntity> observe();

    /** Reads the cache from a non-main thread. */
    DisplayCacheEntity read();

    /** Stores a replacement cache from a non-main thread. */
    void replace(DisplayCacheEntity entity);
}
