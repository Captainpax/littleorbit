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
    private static final String PATH = "/little-orbit/display-v1";

    @Override
    public void onDataChanged(DataEventBuffer events) {
        for (DataEvent event : events) {
            if (event.getType() == DataEvent.TYPE_CHANGED
                    && PATH.equals(event.getDataItem().getUri().getPath())) {
                store(DataMapItem.fromDataItem(event.getDataItem()).getDataMap());
            }
        }
    }

    private void store(DataMap map) {
        WearDisplayCache.store(
                this,
                map.getLong("together_seconds"),
                map.getString("countdown_title", "No countdown yet"),
                map.getLong("countdown_at"),
                map.getLong("updated_at"));
        TileService.getUpdater(this).requestUpdate(LittleOrbitTileService.class);
        ComplicationDataSourceUpdateRequester.create(
                        this, new ComponentName(this, TogetherComplicationService.class))
                .requestUpdateAll();
    }
}
