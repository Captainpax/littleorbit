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
    private static final Duration EXPIRE_AFTER = Duration.ofHours(24);
    private static final int COMPACT_BELOW_DP = 180;

    private WidgetViews() {}

    static RemoteViews render(Context context, DisplayCacheEntity cache) {
        return render(context, cache, false);
    }

    static RemoteViews render(
            Context context, DisplayCacheEntity cache, boolean compact) {
        int layout = compact
                ? R.layout.little_orbit_widget_compact : R.layout.little_orbit_widget;
        RemoteViews views = new RemoteViews(context.getPackageName(), layout);
        views.setOnClickPendingIntent(
                R.id.widget_root,
                compact ? LittleOrbitWidgetProvider.refresh(context)
                        : LittleOrbitWidgetProvider.openApp(context));
        if (compact) {
            views.setOnClickPendingIntent(
                    R.id.widget_countdown, LittleOrbitWidgetProvider.openApp(context));
        } else {
            views.setOnClickPendingIntent(
                    R.id.widget_refresh, LittleOrbitWidgetProvider.refresh(context));
        }
        Instant now = Instant.now();
        if (cache == null || isExpired(cache, now)) {
            renderUnavailable(context, views, compact);
            return views;
        }
        renderAvailable(context, views, cache, now, compact);
        return views;
    }

    static boolean isCompact(int minHeightDp) {
        return minHeightDp > 0 && minHeightDp < COMPACT_BELOW_DP;
    }

    private static void renderAvailable(
            Context context,
            RemoteViews views,
            DisplayCacheEntity cache,
            Instant now,
            boolean compact) {
        String relationship = localizedRelationship(
                context, cache, LocalDate.now(ZoneOffset.UTC));
        long nearbyHours = Duration.ofSeconds(cache.nearbySeconds).toHours();
        String nearby = context.getResources().getQuantityString(
                R.plurals.widget_nearby_hours, quantity(nearbyHours), nearbyHours);
        String countdown = cache.nextCountdownTitle == null || cache.nextCountdownTitle.isBlank()
                ? context.getString(R.string.widget_open_to_refresh) : cache.nextCountdownTitle;
        boolean stale = isStale(cache, now);
        views.setTextViewText(R.id.widget_together, relationship);
        views.setTextViewText(R.id.widget_nearby, nearby);
        views.setTextViewText(R.id.widget_countdown, countdown);
        views.setTextViewText(
                R.id.widget_stale,
                context.getString(compact
                        ? R.string.widget_stale_compact : R.string.widget_stale));
        views.setViewVisibility(R.id.widget_stale, stale ? View.VISIBLE : View.GONE);
        String summary = context.getString(
                R.string.widget_accessibility_summary,
                relationship,
                nearby,
                countdown,
                stale ? context.getString(R.string.widget_accessibility_stale) : "");
        views.setContentDescription(
                R.id.widget_root,
                compact ? context.getString(
                        R.string.widget_accessibility_compact_action, summary) : summary);
        if (compact) {
            views.setContentDescription(
                    R.id.widget_countdown,
                    context.getString(R.string.widget_accessibility_open, countdown));
        }
    }

    static boolean isStale(DisplayCacheEntity cache, Instant now) {
        return cache.cacheSyncedAtEpochMillis == 0
                || Instant.ofEpochMilli(cache.cacheSyncedAtEpochMillis)
                        .plus(STALE_AFTER).isBefore(now)
                || (cache.nearbyProcessedAtEpochMillis > 0
                && Instant.ofEpochMilli(cache.nearbyProcessedAtEpochMillis)
                        .plus(STALE_AFTER).isBefore(now));
    }

    static boolean isExpired(DisplayCacheEntity cache, Instant now) {
        return cache.cacheSyncedAtEpochMillis <= 0
                || !Instant.ofEpochMilli(cache.cacheSyncedAtEpochMillis)
                        .plus(EXPIRE_AFTER).isAfter(now);
    }

    static String relationshipText(DisplayCacheEntity cache, LocalDate today) {
        if (cache.relationshipStartEpochDay < 0) return "Pair to start your orbit";
        long days = Math.max(0, today.toEpochDay() - cache.relationshipStartEpochDay);
        return days + " days together";
    }

    private static String localizedRelationship(
            Context context, DisplayCacheEntity cache, LocalDate today) {
        if (cache.relationshipStartEpochDay < 0) {
            return context.getString(R.string.widget_pair_to_start);
        }
        long days = Math.max(0, today.toEpochDay() - cache.relationshipStartEpochDay);
        return context.getResources().getQuantityString(
                R.plurals.widget_days_together, quantity(days), days);
    }

    private static int quantity(long value) {
        return value > Integer.MAX_VALUE ? Integer.MAX_VALUE : (int) value;
    }

    private static void renderUnavailable(
            Context context, RemoteViews views, boolean compact) {
        views.setTextViewText(
                R.id.widget_together, context.getString(R.string.widget_together_unavailable));
        views.setTextViewText(
                R.id.widget_nearby, context.getString(R.string.widget_nearby_unavailable));
        views.setTextViewText(
                R.id.widget_countdown, context.getString(R.string.widget_open_to_refresh));
        views.setTextViewText(
                R.id.widget_stale,
                context.getString(compact
                        ? R.string.widget_unavailable_compact : R.string.widget_unavailable));
        views.setViewVisibility(R.id.widget_stale, View.VISIBLE);
        String unavailable = context.getString(R.string.widget_accessibility_unavailable);
        views.setContentDescription(
                R.id.widget_root,
                compact ? context.getString(
                        R.string.widget_accessibility_compact_action, unavailable) : unavailable);
        if (compact) {
            views.setContentDescription(
                    R.id.widget_countdown,
                    context.getString(
                            R.string.widget_accessibility_open,
                            context.getString(R.string.widget_open_to_refresh)));
        }
    }
}
