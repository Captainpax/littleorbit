package com.littleorbit.wear;

import com.google.android.gms.wearable.Asset;
import com.google.android.gms.wearable.DataEvent;
import com.google.android.gms.wearable.DataEventBuffer;
import com.google.android.gms.wearable.DataMap;
import com.google.android.gms.wearable.DataMapItem;
import com.google.android.gms.wearable.Wearable;
import com.google.android.gms.wearable.WearableListenerService;
import java.io.IOException;
import java.io.InputStream;
import java.util.ArrayList;
import java.util.List;

/** Receives relationship-scoped passive cache records from the paired phone. */
public final class WearSyncService extends WearableListenerService {
    private static final String PATH_V1 = "/little-orbit/display-v1";
    private static final String PATH_V2 = "/little-orbit/display-v2";
    private static final String PROFILE_PATH = "/little-orbit/profile-v1";
    private static final String PURGE_PATH = "/little-orbit/relationship-purge-v1";

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
        if (PATH_V2.equals(item.path())) return storeDisplay(item.map());
        if (PATH_V1.equals(item.path())) return storeV1(item.map());
        if (PROFILE_PATH.equals(item.path())) return storeProfile(item.map());
        return false;
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
        int schema = map.getInt("schema_version");
        String relationshipId = map.getString("relationship_id", "");
        long generation = map.getLong("relationship_generation");
        long authorizedAt = map.getLong("authorized_at");
        Asset myPhoto = map.getAsset("my_photo");
        Asset partnerPhoto = map.getAsset("partner_photo");
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
        fetchPhoto(myPhoto, false, relationshipId, generation, schema);
        fetchPhoto(partnerPhoto, true, relationshipId, generation, schema);
        return true;
    }

    private void fetchPhoto(
            Asset asset, boolean partner, String relationshipId, long generation, int schema) {
        if (asset == null) {
            return;
        }
        Wearable.getDataClient(this).getFdForAsset(asset).addOnSuccessListener(response -> {
            InputStream input = response.getInputStream();
            if (input == null) return;
            try {
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
        return WearRelationshipGuard.purge(
                this,
                map.getString("relationship_id", ""),
                map.getLong("relationship_generation"),
                now());
    }

    private static boolean supported(String path) {
        return PATH_V1.equals(path) || PATH_V2.equals(path)
                || PROFILE_PATH.equals(path) || PURGE_PATH.equals(path);
    }

    private static void close(InputStream input) {
        if (input == null) return;
        try { input.close(); } catch (IOException ignored) { }
    }

    private static long now() { return System.currentTimeMillis(); }

    private record Incoming(String path, DataMap map) {
        boolean isPurge() {
            if (PURGE_PATH.equals(path)) return true;
            boolean scopedDisplay = PATH_V2.equals(path) && map.getInt("schema_version") >= 3;
            boolean scopedProfile = PROFILE_PATH.equals(path) && map.getInt("schema_version") >= 2;
            return (scopedDisplay || scopedProfile)
                    && !map.getBoolean("relationship_active", true);
        }
    }
}
