package com.littleorbit.mobile;

import android.content.Context;
import com.littleorbit.data.LocationCollectionWorker;
import com.littleorbit.data.remote.ApiModels;

/** Reconciles granted permissions and both server-side consent states with location work. */
final class NearbyTrackingReconciler {
    private NearbyTrackingReconciler() {}

    static void apply(Context context, ApiModels.Preferences preferences) {
        boolean permitted = PermissionChecks.fineLocationGranted(context)
                && PermissionChecks.backgroundLocationGranted(context);
        boolean collect = permitted && preferences.locationByMe;
        LocationCollectionWorker.schedule(context, collect);
        if (collect && preferences.locationByBoth) ForegroundLocationService.start(context);
        else ForegroundLocationService.stop(context);
    }
}
