package com.littleorbit.wear;

import android.content.ComponentName;
import androidx.wear.tiles.TileService;
import androidx.wear.watchface.complications.datasource.ComplicationDataSourceUpdateRequester;
import com.google.android.gms.wearable.DataEvent;
import com.google.android.gms.wearable.DataEventBuffer;
import com.google.android.gms.wearable.DataMap;
import com.google.android.gms.wearable.DataMapItem;
import com.google.android.gms.wearable.Asset;
import com.google.android.gms.wearable.Wearable;
import com.google.android.gms.wearable.WearableListenerService;

/** Receives the privacy-minimal display cache from the paired phone. */
public final class WearSyncService extends WearableListenerService {
    private static final String PATH_V1 = "/little-orbit/display-v1";
    private static final String PATH_V2 = "/little-orbit/display-v2";
    private static final String PROFILE_PATH = "/little-orbit/profile-v1";

    @Override
    public void onDataChanged(DataEventBuffer events) {
        for (DataEvent event : events) {
            String path = event.getDataItem().getUri().getPath();
            if (event.getType() == DataEvent.TYPE_CHANGED && PATH_V2.equals(path)) {
                storeV2(DataMapItem.fromDataItem(event.getDataItem()).getDataMap());
            } else if (event.getType() == DataEvent.TYPE_CHANGED && PATH_V1.equals(path)) {
                storeLegacy(DataMapItem.fromDataItem(event.getDataItem()).getDataMap());
            } else if (event.getType() == DataEvent.TYPE_CHANGED && PROFILE_PATH.equals(path)) {
                storeProfile(DataMapItem.fromDataItem(event.getDataItem()).getDataMap());
            }
        }
    }

    private void storeProfile(DataMap map) {
        WearProfileStore.storeNames(
                this, map.getString("my_name", "You"), map.getString("partner_name", ""));
        fetchPhoto(map.getAsset("my_photo"), false);
        fetchPhoto(map.getAsset("partner_photo"), true);
    }

    private void fetchPhoto(Asset asset, boolean partner) {
        if (asset == null) {
            WearProfileStore.clearPhoto(this, partner);
            return;
        }
        Wearable.getDataClient(this).getFdForAsset(asset).addOnSuccessListener(response -> {
            try {
                WearProfileStore.storePhoto(this, partner, response.getInputStream());
            } catch (java.io.IOException ignored) {
                // Keep the last valid private thumbnail when a transfer is interrupted.
            }
        });
    }

    private void storeV2(DataMap map) {
        WearDisplayCache.storeV2(
                this,
                map.getLong("relationship_start_epoch_day", -1),
                map.getLong("nearby_seconds"),
                map.getLong("nearby_processed_at"),
                map.getString("countdown_title", "No countdown yet"),
                map.getLong("countdown_at"),
                map.getLong("synced_at"));
        requestSurfaceUpdates();
    }

    private void storeLegacy(DataMap map) {
        WearDisplayCache.storeLegacy(
                this,
                map.getLong("together_seconds"),
                map.getString("countdown_title", "No countdown yet"),
                map.getLong("countdown_at"),
                map.getLong("updated_at"));
        requestSurfaceUpdates();
    }

    private void requestSurfaceUpdates() {
        TileService.getUpdater(this).requestUpdate(LittleOrbitTileService.class);
        ComplicationDataSourceUpdateRequester.create(
                        this, new ComponentName(this, TogetherComplicationService.class))
                .requestUpdateAll();
    }
}
