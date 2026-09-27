package com.littleorbit.wear;

import android.content.ComponentName;
import android.content.Context;
import androidx.wear.tiles.TileService;
import androidx.wear.watchface.complications.datasource.ComplicationDataSourceUpdateRequester;

/** Refreshes every passive Wear surface after cache authorization changes. */
final class WearSurfaceUpdates {
    private WearSurfaceUpdates() {}

    static void request(Context context) {
        TileService.getUpdater(context).requestUpdate(LittleOrbitTileService.class);
        ComplicationDataSourceUpdateRequester.create(
                        context, new ComponentName(context, TogetherComplicationService.class))
                .requestUpdateAll();
        ComplicationDataSourceUpdateRequester.create(
                        context, new ComponentName(context, CountdownComplicationService.class))
                .requestUpdateAll();
    }
}
