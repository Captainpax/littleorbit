package com.littleorbit.widget;

import android.appwidget.AppWidgetManager;
import android.appwidget.AppWidgetProvider;
import android.content.Context;
import android.widget.RemoteViews;
import androidx.room.Room;
import com.littleorbit.data.local.DisplayCacheEntity;
import com.littleorbit.data.local.DatabaseMigrations;
import com.littleorbit.data.local.LittleOrbitDatabase;
import java.time.Duration;
import java.time.Instant;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;

/** Home widget that renders only the minimal cache and always exposes staleness. */
public final class LittleOrbitWidgetProvider extends AppWidgetProvider {
    @Override
    public void onUpdate(Context context, AppWidgetManager manager, int[] widgetIds) {
        var pendingResult = goAsync();
        ExecutorService reader = Executors.newSingleThreadExecutor();
        reader.execute(() -> {
            try {
                LittleOrbitDatabase database = Room.databaseBuilder(
                        context.getApplicationContext(), LittleOrbitDatabase.class, "little-orbit.db")
                        .addMigrations(DatabaseMigrations.MIGRATION_1_2)
                        .addMigrations(DatabaseMigrations.MIGRATION_2_3)
                        .build();
                DisplayCacheEntity cache = database.displayCache().read();
                for (int widgetId : widgetIds) {
                    manager.updateAppWidget(widgetId, render(context, cache));
                }
                database.close();
            } finally {
                pendingResult.finish();
                reader.shutdown();
            }
        });
    }

    private RemoteViews render(Context context, DisplayCacheEntity cache) {
        RemoteViews views = new RemoteViews(context.getPackageName(), R.layout.little_orbit_widget);
        if (cache == null) {
            views.setTextViewText(R.id.widget_together, "Together-time unavailable");
            views.setTextViewText(R.id.widget_countdown, "Open Little Orbit to refresh");
            views.setViewVisibility(R.id.widget_stale, android.view.View.VISIBLE);
            return views;
        }
        views.setTextViewText(R.id.widget_together, Duration.ofSeconds(cache.togetherSeconds).toDays() + " days together");
        views.setTextViewText(R.id.widget_countdown, cache.nextCountdownTitle);
        boolean stale = Instant.ofEpochMilli(cache.updatedAtEpochMillis).plus(Duration.ofHours(6)).isBefore(Instant.now());
        views.setViewVisibility(R.id.widget_stale, stale ? android.view.View.VISIBLE : android.view.View.GONE);
        return views;
    }
}
