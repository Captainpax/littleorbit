package com.littleorbit.data;

import android.content.Context;
import com.google.android.gms.wearable.PutDataMapRequest;
import com.google.android.gms.wearable.Wearable;
import com.littleorbit.data.local.DisplayCacheEntity;
import dagger.hilt.android.qualifiers.ApplicationContext;
import javax.inject.Inject;
import javax.inject.Singleton;
import java.time.LocalDate;
import java.time.ZoneOffset;

/** Publishes only the minimal display cache to a paired Wear OS device. */
@Singleton
public final class WearCachePublisher {
    public static final String PATH_V1 = "/little-orbit/display-v1";
    public static final String PATH_V2 = "/little-orbit/display-v2";
    private final Context context;

    /** Creates the paired-device boundary without access to tokens or relationship content. */
    @Inject
    public WearCachePublisher(@ApplicationContext Context context) {
        this.context = context;
    }

    /** Sends a replacement cache record; repeated records are safe. */
    public void publish(DisplayCacheEntity cache) {
        PutDataMapRequest map = PutDataMapRequest.create(PATH_V2);
        map.getDataMap().putInt("schema_version", 2);
        map.getDataMap().putLong(
                "relationship_start_epoch_day", cache.relationshipStartEpochDay);
        map.getDataMap().putLong("nearby_seconds", cache.nearbySeconds);
        map.getDataMap().putLong(
                "nearby_processed_at", cache.nearbyProcessedAtEpochMillis);
        map.getDataMap().putString("countdown_title", cache.nextCountdownTitle);
        map.getDataMap().putLong("countdown_at", cache.nextCountdownEpochMillis);
        map.getDataMap().putLong("synced_at", cache.cacheSyncedAtEpochMillis);
        Wearable.getDataClient(context).putDataItem(map.asPutDataRequest().setUrgent());
        publishLegacy(cache);
    }

    private void publishLegacy(DisplayCacheEntity cache) {
        PutDataMapRequest map = PutDataMapRequest.create(PATH_V1);
        long relationshipSeconds = cache.relationshipStartEpochDay < 0
                ? 0
                : Math.max(
                        0,
                        LocalDate.now(ZoneOffset.UTC).toEpochDay()
                                - cache.relationshipStartEpochDay)
                        * 86_400;
        map.getDataMap().putLong("together_seconds", relationshipSeconds);
        map.getDataMap().putString("countdown_title", cache.nextCountdownTitle);
        map.getDataMap().putLong("countdown_at", cache.nextCountdownEpochMillis);
        map.getDataMap().putLong("updated_at", cache.cacheSyncedAtEpochMillis);
        Wearable.getDataClient(context).putDataItem(map.asPutDataRequest().setUrgent());
    }

    /** Replaces prior relationship values with an explicitly unavailable watch state. */
    public void clear() {
        publish(new DisplayCacheEntity("primary", -1, 0, 0, "No countdown yet", 0, 0));
    }
}
