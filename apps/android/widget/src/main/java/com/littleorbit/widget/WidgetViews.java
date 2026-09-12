package com.littleorbit.widget;

import android.content.Context;
import android.view.View;
import android.widget.RemoteViews;
import com.littleorbit.data.local.DisplayCacheEntity;
import java.time.Duration;
import java.time.Instant;
import java.time.LocalDate;
import java.time.ZoneOffset;

/** Builds privacy-minimal widget views from one immutable cache snapshot. */
final class WidgetViews {
    private static final Duration STALE_AFTER = Duration.ofHours(6);

    private WidgetViews() {}

    static RemoteViews render(Context context, DisplayCacheEntity cache) {
        RemoteViews views = new RemoteViews(context.getPackageName(), R.layout.little_orbit_widget);
        views.setOnClickPendingIntent(R.id.widget_root, LittleOrbitWidgetProvider.openApp(context));
        views.setOnClickPendingIntent(R.id.widget_refresh, LittleOrbitWidgetProvider.refresh(context));
        if (cache == null) {
            renderUnavailable(views);
            return views;
        }
        views.setTextViewText(R.id.widget_together, relationshipText(cache, LocalDate.now(ZoneOffset.UTC)));
        views.setTextViewText(
                R.id.widget_nearby,
                Duration.ofSeconds(cache.nearbySeconds).toHours() + "h nearby · estimate");
        views.setTextViewText(R.id.widget_countdown, cache.nextCountdownTitle);
        views.setViewVisibility(
                R.id.widget_stale, isStale(cache, Instant.now()) ? View.VISIBLE : View.GONE);
        return views;
    }

    static boolean isStale(DisplayCacheEntity cache, Instant now) {
        return cache.cacheSyncedAtEpochMillis == 0
                || Instant.ofEpochMilli(cache.cacheSyncedAtEpochMillis)
                        .plus(STALE_AFTER).isBefore(now)
                || cache.nearbyProcessedAtEpochMillis == 0
                || Instant.ofEpochMilli(cache.nearbyProcessedAtEpochMillis)
                        .plus(STALE_AFTER).isBefore(now);
    }

    static String relationshipText(DisplayCacheEntity cache, LocalDate today) {
        if (cache.relationshipStartEpochDay < 0) {
            return "Set your start date";
        }
        long days = Math.max(0, today.toEpochDay() - cache.relationshipStartEpochDay);
        return days + " days together";
    }

    private static void renderUnavailable(RemoteViews views) {
        views.setTextViewText(R.id.widget_together, "Together-time unavailable");
        views.setTextViewText(R.id.widget_nearby, "Nearby estimate unavailable");
        views.setTextViewText(R.id.widget_countdown, "Open Little Orbit to refresh");
        views.setViewVisibility(R.id.widget_stale, View.VISIBLE);
    }
}
