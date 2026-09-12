package com.littleorbit.widget;

import android.app.PendingIntent;
import android.appwidget.AppWidgetManager;
import android.appwidget.AppWidgetProvider;
import android.content.Context;
import android.content.Intent;
import com.littleorbit.data.DisplayCacheSynchronizer;
import com.littleorbit.data.DisplayCacheSyncWorker;

/** Receives widget events and delegates all asynchronous rendering to WorkManager. */
public final class LittleOrbitWidgetProvider extends AppWidgetProvider {
    static final String ACTION_REFRESH = "com.littleorbit.action.REFRESH_WIDGET";

    @Override
    public void onReceive(Context context, Intent intent) {
        String action = intent.getAction();
        if (ACTION_REFRESH.equals(action)) {
            DisplayCacheSyncWorker.enqueue(context);
            WidgetRenderWorker.enqueue(context);
            return;
        }
        if (DisplayCacheSynchronizer.ACTION_CACHE_UPDATED.equals(action)) {
            WidgetRenderWorker.enqueue(context);
            return;
        }
        super.onReceive(context, intent);
    }

    @Override
    public void onUpdate(Context context, AppWidgetManager manager, int[] widgetIds) {
        WidgetRenderWorker.enqueue(context);
    }

    static PendingIntent openApp(Context context) {
        Intent intent = new Intent().setClassName(
                context.getPackageName(), "com.littleorbit.mobile.MainActivity");
        return PendingIntent.getActivity(
                context, 70, intent, PendingIntent.FLAG_UPDATE_CURRENT | PendingIntent.FLAG_IMMUTABLE);
    }

    static PendingIntent refresh(Context context) {
        Intent intent = new Intent(context, LittleOrbitWidgetProvider.class)
                .setAction(ACTION_REFRESH);
        return PendingIntent.getBroadcast(
                context, 71, intent, PendingIntent.FLAG_UPDATE_CURRENT | PendingIntent.FLAG_IMMUTABLE);
    }
}
