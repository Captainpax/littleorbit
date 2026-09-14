package com.littleorbit.mobile;

import android.content.BroadcastReceiver;
import android.content.Context;
import android.content.Intent;

/** Re-fetches private reminder state after reboot, app update, clock, or timezone changes. */
public final class CountdownClockReceiver extends BroadcastReceiver {
    @Override
    public void onReceive(Context context, Intent intent) {
        PartnerNotificationWorker.enqueue(context);
    }
}
