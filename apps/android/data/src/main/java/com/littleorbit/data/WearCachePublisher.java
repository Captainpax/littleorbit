package com.littleorbit.data;

import android.content.Context;
import com.google.android.gms.wearable.PutDataMapRequest;
import com.google.android.gms.wearable.Wearable;
import com.littleorbit.data.local.DisplayCacheEntity;
import dagger.hilt.android.qualifiers.ApplicationContext;
import javax.inject.Inject;
import javax.inject.Singleton;

/** Publishes only the minimal display cache to a paired Wear OS device. */
@Singleton
public final class WearCachePublisher {
    public static final String PATH = "/little-orbit/display-v1";
    private final Context context;

    /** Creates the paired-device boundary without access to tokens or relationship content. */
    @Inject
    public WearCachePublisher(@ApplicationContext Context context) {
        this.context = context;
    }

    /** Sends a replacement cache record; repeated records are safe. */
    public void publish(DisplayCacheEntity cache) {
        PutDataMapRequest map = PutDataMapRequest.create(PATH);
        map.getDataMap().putLong("together_seconds", cache.togetherSeconds);
        map.getDataMap().putString("countdown_title", cache.nextCountdownTitle);
        map.getDataMap().putLong("countdown_at", cache.nextCountdownEpochMillis);
        map.getDataMap().putLong("updated_at", cache.updatedAtEpochMillis);
        Wearable.getDataClient(context).putDataItem(map.asPutDataRequest().setUrgent());
    }
}
