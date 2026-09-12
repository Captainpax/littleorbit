package com.littleorbit.wear;

import android.content.ComponentName;
import androidx.wear.tiles.TileService;
import androidx.wear.watchface.complications.datasource.ComplicationDataSourceUpdateRequester;
import com.google.android.gms.wearable.DataEvent;
import com.google.android.gms.wearable.DataEventBuffer;
import com.google.android.gms.wearable.DataMap;
import com.google.android.gms.wearable.DataMapItem;
import com.google.android.gms.wearable.WearableListenerService;

/** Receives the privacy-minimal display cache from the paired phone. */
public final class WearSyncService extends WearableListenerService {
    private static final String PATH_V1 = "/little-orbit/display-v1";
    private static final String PATH_V2 = "/little-orbit/display-v2";

    @Override
    public void onDataChanged(DataEventBuffer events) {
        for (DataEvent event : events) {
            String path = event.getDataItem().getUri().getPath();
            if (event.getType() == DataEvent.TYPE_CHANGED && PATH_V2.equals(path)) {
                storeV2(DataMapItem.fromDataItem(event.getDataItem()).getDataMap());
            } else if (event.getType() == DataEvent.TYPE_CHANGED && PATH_V1.equals(path)) {
                storeLegacy(DataMapItem.fromDataItem(event.getDataItem()).getDataMap());
            }
        }
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
