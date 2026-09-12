package com.littleorbit.widget;

import android.app.PendingIntent;
import android.appwidget.AppWidgetManager;
import android.appwidget.AppWidgetProvider;
import android.content.Context;
import android.content.Intent;
import android.widget.RemoteViews;
import androidx.room.Room;
import com.littleorbit.data.DisplayCacheSynchronizer;
import com.littleorbit.data.DisplayCacheSyncWorker;
import com.littleorbit.data.local.DisplayCacheEntity;
import com.littleorbit.data.local.DatabaseMigrations;
import com.littleorbit.data.local.LittleOrbitDatabase;
import java.time.Duration;
import java.time.Instant;
import java.time.LocalDate;
import java.time.ZoneOffset;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;

/** Home widget that renders only the minimal cache and always exposes staleness. */
public final class LittleOrbitWidgetProvider extends AppWidgetProvider {
    private static final String ACTION_REFRESH = "com.littleorbit.action.REFRESH_WIDGET";

    @Override
    public void onReceive(Context context, Intent intent) {
        super.onReceive(context, intent);
        String action = intent.getAction();
        if (ACTION_REFRESH.equals(action)) {
            DisplayCacheSyncWorker.enqueue(context);
            updateAll(context);
        } else if (DisplayCacheSynchronizer.ACTION_CACHE_UPDATED.equals(action)) {
            updateAll(context);
        }
    }

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
                        .addMigrations(DatabaseMigrations.MIGRATION_3_4)
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
        views.setOnClickPendingIntent(R.id.widget_root, openApp(context));
        views.setOnClickPendingIntent(R.id.widget_refresh, refresh(context));
        if (cache == null) {
            views.setTextViewText(R.id.widget_together, "Together-time unavailable");
            views.setTextViewText(R.id.widget_nearby, "Nearby estimate unavailable");
            views.setTextViewText(R.id.widget_countdown, "Open Little Orbit to refresh");
            views.setViewVisibility(R.id.widget_stale, android.view.View.VISIBLE);
            return views;
        }
        views.setTextViewText(R.id.widget_together, relationshipText(cache));
        views.setTextViewText(
                R.id.widget_nearby,
                Duration.ofSeconds(cache.nearbySeconds).toHours() + "h nearby · estimate");
        views.setTextViewText(R.id.widget_countdown, cache.nextCountdownTitle);
        boolean stale = cache.cacheSyncedAtEpochMillis == 0
                || Instant.ofEpochMilli(cache.cacheSyncedAtEpochMillis)
                        .plus(Duration.ofHours(6)).isBefore(Instant.now())
                || cache.nearbyProcessedAtEpochMillis == 0
                || Instant.ofEpochMilli(cache.nearbyProcessedAtEpochMillis)
                        .plus(Duration.ofHours(6)).isBefore(Instant.now());
        views.setViewVisibility(R.id.widget_stale, stale ? android.view.View.VISIBLE : android.view.View.GONE);
        return views;
    }

    private static String relationshipText(DisplayCacheEntity cache) {
        if (cache.relationshipStartEpochDay < 0) {
            return "Set your start date";
        }
        long days = Math.max(
                0,
                LocalDate.now(ZoneOffset.UTC).toEpochDay() - cache.relationshipStartEpochDay);
        return days + " days together";
    }

    private static PendingIntent openApp(Context context) {
        Intent intent = new Intent().setClassName(
                context.getPackageName(), "com.littleorbit.mobile.MainActivity");
        return PendingIntent.getActivity(
                context, 70, intent, PendingIntent.FLAG_UPDATE_CURRENT | PendingIntent.FLAG_IMMUTABLE);
    }

    private static PendingIntent refresh(Context context) {
        Intent intent = new Intent(context, LittleOrbitWidgetProvider.class)
                .setAction(ACTION_REFRESH);
        return PendingIntent.getBroadcast(
                context, 71, intent, PendingIntent.FLAG_UPDATE_CURRENT | PendingIntent.FLAG_IMMUTABLE);
    }

    private static void updateAll(Context context) {
        AppWidgetManager manager = AppWidgetManager.getInstance(context);
        android.content.ComponentName component =
                new android.content.ComponentName(context, LittleOrbitWidgetProvider.class);
        int[] ids = manager.getAppWidgetIds(component);
        if (ids.length > 0) {
            new LittleOrbitWidgetProvider().onUpdate(context, manager, ids);
        }
    }
}
