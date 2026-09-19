package com.littleorbit.mobile;

import android.content.BroadcastReceiver;
import android.content.Context;
import android.content.Intent;
import com.littleorbit.data.LocationCollectionWorker;

/** Re-arms bounded collection recovery after reboot or an app replacement. */
public final class NearbyRecoveryReceiver extends BroadcastReceiver {
    @Override
    public void onReceive(Context context, Intent intent) {
        String action = intent == null ? null : intent.getAction();
        if (!Intent.ACTION_BOOT_COMPLETED.equals(action)
                && !Intent.ACTION_MY_PACKAGE_REPLACED.equals(action)) return;
        LocationCollectionWorker.schedule(context, true);
    }
}
