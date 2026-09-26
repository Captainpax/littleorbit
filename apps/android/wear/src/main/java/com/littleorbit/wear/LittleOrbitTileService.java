package com.littleorbit.wear;

import androidx.annotation.NonNull;
import androidx.wear.protolayout.LayoutElementBuilders;
import androidx.wear.protolayout.ResourceBuilders;
import androidx.wear.protolayout.TimelineBuilders;
import androidx.wear.tiles.RequestBuilders;
import androidx.wear.tiles.TileBuilders;
import androidx.wear.tiles.TileService;
import com.google.common.util.concurrent.Futures;
import com.google.common.util.concurrent.ListenableFuture;

/** Wear OS tile showing compact cached values with an explicit stale state. */
public final class LittleOrbitTileService extends TileService {
    private static final String RESOURCES_VERSION = "1";

    @NonNull
    @Override
    protected ListenableFuture<TileBuilders.Tile> onTileRequest(@NonNull RequestBuilders.TileRequest request) {
        WearDisplayCache.State cache = WearDisplayCache.read(this);
        WearDisplayText display = new WearDisplayText(this);
        LayoutElementBuilders.Column column = new LayoutElementBuilders.Column.Builder()
                .addContent(text(getString(R.string.tile_eyebrow)))
                .addContent(text(display.nearby(cache)))
                .addContent(text(display.status(cache)))
                .build();
        LayoutElementBuilders.Layout layout =
                new LayoutElementBuilders.Layout.Builder().setRoot(column).build();
        TileBuilders.Tile tile = new TileBuilders.Tile.Builder()
                .setResourcesVersion(RESOURCES_VERSION)
                .setTileTimeline(new TimelineBuilders.Timeline.Builder()
                        .addTimelineEntry(new TimelineBuilders.TimelineEntry.Builder().setLayout(layout).build())
                        .build())
                .build();
        return Futures.immediateFuture(tile);
    }

    private static LayoutElementBuilders.Text text(String value) {
        return new LayoutElementBuilders.Text.Builder().setText(value).build();
    }

    @NonNull
    @Override
    protected ListenableFuture<ResourceBuilders.Resources> onTileResourcesRequest(
            @NonNull RequestBuilders.ResourcesRequest request) {
        return Futures.immediateFuture(new ResourceBuilders.Resources.Builder()
                .setVersion(RESOURCES_VERSION)
                .build());
    }
}
