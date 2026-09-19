package com.littleorbit.wear;

import com.google.android.gms.wearable.Asset;
import com.google.android.gms.wearable.DataEvent;
import com.google.android.gms.wearable.DataEventBuffer;
import com.google.android.gms.wearable.DataMap;
import com.google.android.gms.wearable.DataMapItem;
import com.google.android.gms.wearable.Wearable;
import com.google.android.gms.wearable.WearableListenerService;
import com.google.android.gms.tasks.Tasks;
import java.io.IOException;
import java.io.InputStream;
import java.util.ArrayList;
import java.util.List;
import java.util.concurrent.TimeUnit;

/** Receives relationship-scoped passive cache records from the paired phone. */
public final class WearSyncService extends WearableListenerService {
    private static final String PATH_V1 = "/little-orbit/display-v1";
    private static final String PATH_V2 = "/little-orbit/display-v2";
    private static final String PROFILE_PATH = "/little-orbit/profile-v1";
    private static final String PURGE_PATH = "/little-orbit/relationship-purge-v1";
    private static final String MANAGED_DISPLAY_PATH = "/little-orbit/watch-display-v1";
    private static final String MANAGED_PROFILE_PATH = "/little-orbit/watch-profile-v1";
    private static final String CONFIG_PATH = "/little-orbit/watch-config-v1";
    private static final String MANAGED_PURGE_PATH = "/little-orbit/watch-purge-v1";

    @Override
    public void onDataChanged(DataEventBuffer events) {
        List<Incoming> incoming = changedItems(events);
        boolean changed = false;
        // Data Layer ordering is only guaranteed per path. Apply every durable purge first.
        for (Incoming item : incoming) {
            if (item.isPurge()) changed |= purge(item.map());
        }
        for (Incoming item : incoming) {
            if (!item.isPurge()) changed |= store(item);
        }
        if (changed) WearSurfaceUpdates.request(this);
    }

    private List<Incoming> changedItems(DataEventBuffer events) {
        List<Incoming> result = new ArrayList<>();
        for (DataEvent event : events) {
            String path = event.getDataItem().getUri().getPath();
            if (event.getType() == DataEvent.TYPE_CHANGED && supported(path)) {
                result.add(new Incoming(
                        path, DataMapItem.fromDataItem(event.getDataItem()).getDataMap()));
            }
        }
        return result;
    }

    private boolean store(Incoming item) {
        if (MANAGED_DISPLAY_PATH.equals(item.path())) return storeManagedDisplay(item.map());
        if (MANAGED_PROFILE_PATH.equals(item.path())) return storeManagedProfile(item.map());
        if (CONFIG_PATH.equals(item.path())) return storeConfiguration(item.map());
        if (PATH_V2.equals(item.path())) return storeDisplay(item.map());
        if (PATH_V1.equals(item.path())) return storeV1(item.map());
        if (PROFILE_PATH.equals(item.path())) return storeProfile(item.map());
        return false;
    }

    private boolean storeManagedDisplay(DataMap map) {
        Target target = target(map);
        if (target == null || !WearTargetGuard.accept(
                this, localNodeId(), target.nodeId(), target.generation())) return false;
        String relationshipId = map.getString("relationship_id", "");
        long relationshipGeneration = map.getLong("relationship_generation");
        long authorizedAt = map.getLong("authorized_at");
        long syncedAt = map.getLong("synced_at");
        if (syncedAt <= 0) return false;
        return WearRelationshipGuard.acceptActiveAndRun(
                this, relationshipId, relationshipGeneration, authorizedAt, now(), () ->
                        WearDisplayCache.storeV2(
                                this, map.getLong("relationship_start_epoch_day", -1),
                                map.getLong("nearby_seconds"),
                                map.getLong("nearby_processed_at"),
                                map.getString("countdown_title", ""),
                                map.getLong("countdown_at"),
                                map.getString("countdown_timing_kind", "timed"),
                                map.getString("countdown_occurs_on", ""),
                                map.getString("countdown_timezone", "UTC"), syncedAt));
    }

    private boolean storeConfiguration(DataMap map) {
        Target target = target(map);
        if (target == null || !WearTargetGuard.accept(
                this, localNodeId(), target.nodeId(), target.generation())) return false;
        String relationshipId = map.getString("relationship_id", "");
        long relationshipGeneration = map.getLong("relationship_generation");
        long authorizedAt = map.getLong("authorized_at");
        return WearRelationshipGuard.acceptActiveAndRun(
                this, relationshipId, relationshipGeneration, authorizedAt, now(), () ->
                        WearConfiguration.store(this,
                                map.getBoolean("show_photos", true),
                                map.getBoolean("show_countdown_titles", true),
                                map.getBoolean("smooch_enabled", false),
                                map.getString("default_destination", "together")));
    }

    private boolean storeDisplay(DataMap map) {
        if (map.getInt("schema_version") >= 3) return storeV3(map);
        long syncedAt = map.getLong("synced_at");
        if (syncedAt <= 0) return WearRelationshipGuard.purgeLegacy(this, now());
        return WearRelationshipGuard.acceptLegacyAndRun(this, syncedAt, now(), () ->
                WearDisplayCache.storeV2(
                        this,
                        map.getLong("relationship_start_epoch_day", -1),
                        map.getLong("nearby_seconds"),
                        map.getLong("nearby_processed_at"),
                        map.getString("countdown_title", "No countdown yet"),
                        map.getLong("countdown_at"),
                        "timed", "", "UTC",
                        syncedAt));
    }

    private boolean storeV3(DataMap map) {
        String relationshipId = map.getString("relationship_id", "");
        long generation = map.getLong("relationship_generation");
        long authorizedAt = map.getLong("authorized_at");
        long syncedAt = map.getLong("synced_at");
        long startDay = map.getLong("relationship_start_epoch_day", -1);
        if (syncedAt <= 0 || startDay < 0) return false;
        return WearRelationshipGuard.acceptActiveAndRun(
                this, relationshipId, generation, authorizedAt, now(),
                () -> WearDisplayCache.storeV2(
                        this, startDay,
                        map.getLong("nearby_seconds"),
                        map.getLong("nearby_processed_at"),
                        map.getString("countdown_title", "No countdown yet"),
                        map.getLong("countdown_at"),
                        "timed", "", "UTC",
                        syncedAt));
    }

    private boolean storeV1(DataMap map) {
        long updatedAt = map.getLong("updated_at");
        if (updatedAt <= 0) return WearRelationshipGuard.purgeLegacy(this, now());
        return WearRelationshipGuard.acceptLegacyAndRun(this, updatedAt, now(), () ->
                WearDisplayCache.storeLegacy(
                        this,
                        map.getLong("together_seconds"),
                        map.getString("countdown_title", "No countdown yet"),
                        map.getLong("countdown_at"),
                        updatedAt));
    }

    private boolean storeProfile(DataMap map) {
        return storeProfile(map, false);
    }

    private boolean storeManagedProfile(DataMap map) {
        return storeProfile(map, true);
    }

    private boolean storeProfile(DataMap map, boolean managed) {
        int schema = map.getInt("schema_version");
        String relationshipId = map.getString("relationship_id", "");
        long generation = map.getLong("relationship_generation");
        long authorizedAt = map.getLong("authorized_at");
        Asset myPhoto = map.getAsset("my_photo");
        Asset partnerPhoto = map.getAsset("partner_photo");
        Target target = managed ? target(map) : null;
        if (managed && (target == null || !WearTargetGuard.accept(
                this, localNodeId(), target.nodeId(), target.generation()))) return false;
        Runnable storeNames = () -> {
            WearProfileStore.storeNames(
                    this, map.getString("my_name", "You"),
                    map.getString("partner_name", ""));
            if (myPhoto == null) WearProfileStore.clearPhoto(this, false);
            if (partnerPhoto == null) WearProfileStore.clearPhoto(this, true);
        };
        boolean accepted = schema >= 2
                ? WearRelationshipGuard.acceptActiveAndRun(
                        this, relationshipId, generation, authorizedAt, now(), storeNames)
                : WearRelationshipGuard.acceptLegacyAndRun(
                        this, map.getLong("changed_at"), now(), storeNames);
        if (!accepted) return false;
        fetchPhoto(myPhoto, false, relationshipId, generation, schema, target);
        fetchPhoto(partnerPhoto, true, relationshipId, generation, schema, target);
        return true;
    }

    private void fetchPhoto(
            Asset asset, boolean partner, String relationshipId, long generation, int schema) {
        fetchPhoto(asset, partner, relationshipId, generation, schema, null);
    }

    private void fetchPhoto(
            Asset asset,
            boolean partner,
            String relationshipId,
            long generation,
            int schema,
            Target target) {
        if (asset == null) {
            return;
        }
        Wearable.getDataClient(this).getFdForAsset(asset).addOnSuccessListener(response -> {
            InputStream input = response.getInputStream();
            if (input == null) return;
            try {
                if (target != null && !WearTargetGuard.isCurrent(
                        this, target.nodeId(), target.generation())) {
                    input.close();
                    return;
                }
                if (WearRelationshipGuard.storePhotoIfAuthorized(
                        this, partner, input, relationshipId, generation, schema)) {
                    WearSurfaceUpdates.request(this);
                }
            } catch (IOException ignored) {
                close(input);
                // Keep the last verified private thumbnail after an interrupted transfer.
            }
        });
    }

    private boolean purge(DataMap map) {
        boolean targetPurged = false;
        if (map.getLong("watch_generation") > 0) {
            targetPurged = WearTargetGuard.purge(this, map.getLong("watch_generation"));
        }
        boolean relationshipPurged = WearRelationshipGuard.purge(
                this,
                map.getString("relationship_id", ""),
                map.getLong("relationship_generation"),
                now());
        return targetPurged || relationshipPurged;
    }

    private static boolean supported(String path) {
        return PATH_V1.equals(path) || PATH_V2.equals(path)
                || PROFILE_PATH.equals(path) || PURGE_PATH.equals(path)
                || MANAGED_DISPLAY_PATH.equals(path) || MANAGED_PROFILE_PATH.equals(path)
                || CONFIG_PATH.equals(path) || MANAGED_PURGE_PATH.equals(path);
    }

    private static void close(InputStream input) {
        if (input == null) return;
        try { input.close(); } catch (IOException ignored) { }
    }

    private static long now() { return System.currentTimeMillis(); }

    private String localNodeId() {
        try {
            return Tasks.await(Wearable.getNodeClient(this).getLocalNode(), 5, TimeUnit.SECONDS)
                    .getId();
        } catch (Exception unavailable) {
            return "";
        }
    }

    private static Target target(DataMap map) {
        String nodeId = map.getString("target_node_id", "");
        long generation = map.getLong("watch_generation");
        return nodeId.isBlank() || generation <= 0 ? null : new Target(nodeId, generation);
    }

    private record Incoming(String path, DataMap map) {
        boolean isPurge() {
            if (PURGE_PATH.equals(path) || MANAGED_PURGE_PATH.equals(path)) return true;
            boolean scopedDisplay = PATH_V2.equals(path) && map.getInt("schema_version") >= 3;
            boolean scopedProfile = (PROFILE_PATH.equals(path) || MANAGED_PROFILE_PATH.equals(path))
                    && map.getInt("schema_version") >= 2;
            return (scopedDisplay || scopedProfile)
                    && !map.getBoolean("relationship_active", true);
        }
    }

    private record Target(String nodeId, long generation) {}
}
