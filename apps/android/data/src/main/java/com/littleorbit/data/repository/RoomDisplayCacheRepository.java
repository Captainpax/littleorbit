package com.littleorbit.data.repository;

import androidx.lifecycle.LiveData;
import com.littleorbit.data.local.DisplayCacheDao;
import com.littleorbit.data.local.DisplayCacheEntity;
import javax.inject.Inject;
import javax.inject.Singleton;

/** Room implementation with no Android UI or network behavior. */
@Singleton
public final class RoomDisplayCacheRepository implements DisplayCacheRepository {
    private final DisplayCacheDao dao;

    /** Creates the repository with its persistence dependency. */
    @Inject
    public RoomDisplayCacheRepository(DisplayCacheDao dao) {
        this.dao = dao;
    }

    @Override public LiveData<DisplayCacheEntity> observe() { return dao.observe(); }
    @Override public DisplayCacheEntity read() { return dao.read(); }
    @Override public void replace(DisplayCacheEntity entity) { dao.replace(entity); }
}
