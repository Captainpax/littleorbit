package com.littleorbit.mobile;

import android.content.BroadcastReceiver;
import android.content.Context;
import android.content.Intent;

/** Re-fetches private reminder state after reboot, app update, clock, or timezone changes. */
public final class CountdownClockReceiver extends BroadcastReceiver {
    @Override
    public void onReceive(Context context, Intent intent) {
        if (!isExpected(intent == null ? null : intent.getAction())) return;
        PartnerNotificationWorker.enqueue(context);
    }

    private static boolean isExpected(String action) {
        return Intent.ACTION_BOOT_COMPLETED.equals(action)
                || Intent.ACTION_MY_PACKAGE_REPLACED.equals(action)
                || Intent.ACTION_TIMEZONE_CHANGED.equals(action)
                || Intent.ACTION_TIME_CHANGED.equals(action);
    }
}
