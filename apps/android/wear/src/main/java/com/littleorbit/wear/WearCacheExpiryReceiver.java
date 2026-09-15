package com.littleorbit.wear;

import android.app.AlarmManager;
import android.app.PendingIntent;
import android.content.BroadcastReceiver;
import android.content.Context;
import android.content.Intent;

/** Performs the bounded best-effort purge alarm and restores it after watch reboot. */
public final class WearCacheExpiryReceiver extends BroadcastReceiver {
    private static final String ACTION_EXPIRE = "com.littleorbit.wear.EXPIRE_CACHE";

    @Override
    public void onReceive(Context context, Intent intent) {
        String action = intent == null ? null : intent.getAction();
        if (!Intent.ACTION_BOOT_COMPLETED.equals(action) && !ACTION_EXPIRE.equals(action)) return;
        boolean expired = WearRelationshipGuard.expireIfNeeded(
                context, System.currentTimeMillis());
        if (expired) WearSurfaceUpdates.request(context);
    }

    static void schedule(Context context, long deadline) {
        if (deadline <= 0) return;
        AlarmManager alarms = (AlarmManager) context.getSystemService(Context.ALARM_SERVICE);
        alarms.setAndAllowWhileIdle(AlarmManager.RTC_WAKEUP, deadline, pending(context));
    }

    static void cancel(Context context) {
        AlarmManager alarms = (AlarmManager) context.getSystemService(Context.ALARM_SERVICE);
        alarms.cancel(pending(context));
    }

    private static PendingIntent pending(Context context) {
        Intent intent = new Intent(context, WearCacheExpiryReceiver.class).setAction(ACTION_EXPIRE);
        return PendingIntent.getBroadcast(
                context, 91, intent,
                PendingIntent.FLAG_UPDATE_CURRENT | PendingIntent.FLAG_IMMUTABLE);
    }
}
