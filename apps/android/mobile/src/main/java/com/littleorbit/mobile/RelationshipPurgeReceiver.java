package com.littleorbit.mobile;

import android.content.BroadcastReceiver;
import android.content.Context;
import android.content.Intent;
import com.littleorbit.data.DisplayCacheSynchronizer;

/** Applies the mobile side of an internal relationship purge signal. */
public final class RelationshipPurgeReceiver extends BroadcastReceiver {
    @Override
    public void onReceive(Context context, Intent intent) {
        if (DisplayCacheSynchronizer.ACTION_RELATIONSHIP_PURGED.equals(intent.getAction())) {
            RelationshipLocalPurge.clear(context);
        }
    }
}
