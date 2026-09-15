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
    public static final String PURGE_PATH = "/little-orbit/relationship-purge-v1";
    private final Context context;

    /** Creates the paired-device boundary without access to tokens or relationship content. */
    @Inject
    public WearCachePublisher(@ApplicationContext Context context) {
        this.context = context;
    }

    /** Sends a replacement cache record; repeated records are safe. */
    public void publish(
            DisplayCacheEntity cache, RelationshipDisplayIdentity.Snapshot relationship) {
        PutDataMapRequest map = PutDataMapRequest.create(PATH_V2);
        map.getDataMap().putInt("schema_version", 3);
        putRelationship(map, relationship, true);
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

    /** Urgently invalidates prior watch data and leaves a durable generation barrier. */
    public void clear(RelationshipDisplayIdentity.Snapshot purge) {
        PutDataMapRequest marker = PutDataMapRequest.create(PURGE_PATH);
        marker.getDataMap().putInt("schema_version", 1);
        putRelationship(marker, purge, false);
        Wearable.getDataClient(context).putDataItem(marker.asPutDataRequest().setUrgent());

        PutDataMapRequest display = PutDataMapRequest.create(PATH_V2);
        display.getDataMap().putInt("schema_version", 3);
        putRelationship(display, purge, false);
        display.getDataMap().putLong("relationship_start_epoch_day", -1);
        display.getDataMap().putLong("nearby_seconds", 0);
        display.getDataMap().putLong("nearby_processed_at", 0);
        display.getDataMap().putString("countdown_title", "No countdown yet");
        display.getDataMap().putLong("countdown_at", 0);
        display.getDataMap().putLong("synced_at", 0);
        Wearable.getDataClient(context).putDataItem(display.asPutDataRequest().setUrgent());
        publishLegacy(new DisplayCacheEntity("primary", -1, 0, 0, "No countdown yet", 0, 0));
    }

    private static void putRelationship(
            PutDataMapRequest request,
            RelationshipDisplayIdentity.Snapshot relationship,
            boolean active) {
        request.getDataMap().putString("relationship_id", relationship.relationshipId());
        request.getDataMap().putLong("relationship_generation", relationship.generation());
        request.getDataMap().putBoolean("relationship_active", active);
        request.getDataMap().putLong("authorized_at", System.currentTimeMillis());
    }
}
