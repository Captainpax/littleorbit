package com.littleorbit.widget;

import android.appwidget.AppWidgetManager;
import android.content.ComponentName;
import android.content.Context;
import android.util.Log;
import androidx.annotation.NonNull;
import androidx.room.Room;
import androidx.work.ExistingWorkPolicy;
import androidx.work.OneTimeWorkRequest;
import androidx.work.WorkManager;
import androidx.work.Worker;
import androidx.work.WorkerParameters;
import com.littleorbit.data.local.DatabaseMigrations;
import com.littleorbit.data.local.DisplayCacheEntity;
import com.littleorbit.data.local.LittleOrbitDatabase;
import com.littleorbit.data.RelationshipDisplayIdentity;

/** Coalesces widget cache reads outside the broadcast receiver lifecycle. */
public final class WidgetRenderWorker extends Worker {
    private static final String TAG = "OrbitWidget";
    private static final String UNIQUE_WORK = "little-orbit-widget-render";

    /** Creates one WorkManager-owned render. */
    public WidgetRenderWorker(@NonNull Context context, @NonNull WorkerParameters parameters) {
        super(context, parameters);
    }

    /** Enqueues the latest render request and replaces obsolete pending work. */
    public static void enqueue(Context context) {
        OneTimeWorkRequest request = new OneTimeWorkRequest.Builder(WidgetRenderWorker.class).build();
        WorkManager.getInstance(context).enqueueUniqueWork(
                UNIQUE_WORK, ExistingWorkPolicy.REPLACE, request);
    }

    @NonNull
    @Override
    public Result doWork() {
        Context context = getApplicationContext();
        AppWidgetManager manager = AppWidgetManager.getInstance(context);
        int[] widgetIds = manager.getAppWidgetIds(
                new ComponentName(context, LittleOrbitWidgetProvider.class));
        if (widgetIds.length == 0) {
            return Result.success();
        }
        DisplayCacheEntity cache = readCache(context);
        try {
            for (int widgetId : widgetIds) {
                int minHeight = manager.getAppWidgetOptions(widgetId).getInt(
                        AppWidgetManager.OPTION_APPWIDGET_MIN_HEIGHT, 0);
                manager.updateAppWidget(
                        widgetId, WidgetViews.render(
                                context, cache, WidgetViews.isCompact(minHeight)));
            }
            return Result.success();
        } catch (RuntimeException failure) {
            Log.e(TAG, "Widget rendering failed", failure);
            return Result.failure();
        }
    }

    private static DisplayCacheEntity readCache(Context context) {
        LittleOrbitDatabase database = null;
        try {
            RelationshipDisplayIdentity identity = new RelationshipDisplayIdentity(context);
            RelationshipDisplayIdentity.Snapshot before = identity.read();
            if (!before.active()) return null;
            database = Room.databaseBuilder(context, LittleOrbitDatabase.class, "little-orbit.db")
                .addMigrations(DatabaseMigrations.MIGRATION_1_2)
                .addMigrations(DatabaseMigrations.MIGRATION_2_3)
                .addMigrations(DatabaseMigrations.MIGRATION_3_4)
                .build();
            DisplayCacheEntity cache = database.displayCache().read();
            RelationshipDisplayIdentity.Snapshot after = identity.read();
            return before.equals(after) && after.active() ? cache : null;
        } catch (RuntimeException failure) {
            Log.e(TAG, "Widget cache read failed; showing unavailable state", failure);
            return null;
        } finally {
            if (database != null) database.close();
        }
    }
}
