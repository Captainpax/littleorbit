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
    public static final String MANAGED_PATH = "/little-orbit/watch-display-v1";
    public static final String MANAGED_PURGE_PATH = "/little-orbit/watch-purge-v1";
    private final Context context;
    private final ManagedWatchStore watches;

    /** Creates the paired-device boundary without access to tokens or relationship content. */
    @Inject
    public WearCachePublisher(@ApplicationContext Context context, ManagedWatchStore watches) {
        this.context = context;
        this.watches = watches;
    }

    /** Sends a replacement cache record; repeated records are safe. */
    public void publish(
            DisplayCacheEntity cache, RelationshipDisplayIdentity.Snapshot relationship) {
        ManagedWatchStore.Snapshot watch = watches.read();
        if (!watch.enabled() || watch.nodeId().isBlank()) return;
        PutDataMapRequest map = PutDataMapRequest.create(MANAGED_PATH);
        map.getDataMap().putInt("schema_version", 1);
        putRelationship(map, relationship, true);
        putTarget(map, watch);
        map.getDataMap().putLong(
                "relationship_start_epoch_day", cache.relationshipStartEpochDay);
        map.getDataMap().putLong("nearby_seconds", cache.nearbySeconds);
        map.getDataMap().putLong(
                "nearby_processed_at", cache.nearbyProcessedAtEpochMillis);
        map.getDataMap().putString("countdown_title",
                watch.showCountdownTitles() ? cache.nextCountdownTitle : "");
        map.getDataMap().putLong("countdown_at", cache.nextCountdownEpochMillis);
        map.getDataMap().putString("countdown_timing_kind", cache.nextCountdownTimingKind);
        map.getDataMap().putString("countdown_occurs_on", cache.nextCountdownOccursOn);
        map.getDataMap().putString("countdown_timezone", cache.nextCountdownTimezone);
        map.getDataMap().putLong("synced_at", cache.cacheSyncedAtEpochMillis);
        Wearable.getDataClient(context).putDataItem(map.asPutDataRequest().setUrgent());
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
        ManagedWatchStore.Snapshot watch = watches.read();
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

        if (watch.nodeId().isBlank()) return;
        PutDataMapRequest managed = PutDataMapRequest.create(MANAGED_PURGE_PATH);
        managed.getDataMap().putInt("schema_version", 1);
        putRelationship(managed, purge, false);
        putTarget(managed, watch);
        Wearable.getDataClient(context).putDataItem(managed.asPutDataRequest().setUrgent());
    }

    /** Clears legacy global payloads before one explicitly selected watch is activated. */
    public void retireLegacy(RelationshipDisplayIdentity.Snapshot purge) {
        clear(purge);
    }

    /** Clears one selected watch even when no relationship is currently active. */
    public void clearTarget(String nodeId, long generation) {
        if (nodeId == null || nodeId.isBlank() || generation <= 0) return;
        PutDataMapRequest managed = PutDataMapRequest.create(MANAGED_PURGE_PATH);
        managed.getDataMap().putInt("schema_version", 1);
        managed.getDataMap().putString("target_node_id", nodeId);
        managed.getDataMap().putLong("watch_generation", generation);
        managed.getDataMap().putString("relationship_id", "");
        managed.getDataMap().putLong("relationship_generation", 0);
        managed.getDataMap().putBoolean("relationship_active", false);
        managed.getDataMap().putLong("authorized_at", System.currentTimeMillis());
        Wearable.getDataClient(context).putDataItem(managed.asPutDataRequest().setUrgent());
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

    private static void putTarget(
            PutDataMapRequest request, ManagedWatchStore.Snapshot watch) {
        request.getDataMap().putString("target_node_id", watch.nodeId());
        request.getDataMap().putLong("watch_generation", watch.generation());
    }
}
