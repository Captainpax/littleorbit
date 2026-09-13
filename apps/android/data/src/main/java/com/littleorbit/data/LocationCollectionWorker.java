package com.littleorbit.data;

import android.content.Context;
import androidx.annotation.NonNull;
import androidx.hilt.work.HiltWorker;
import androidx.work.ExistingPeriodicWorkPolicy;
import androidx.work.PeriodicWorkRequest;
import androidx.work.WorkManager;
import androidx.work.Worker;
import androidx.work.WorkerParameters;
import dagger.assisted.Assisted;
import dagger.assisted.AssistedInject;
import java.util.concurrent.TimeUnit;

/** Balanced-power fallback sampler for periods when foreground tracking cannot run. */
@HiltWorker
public final class LocationCollectionWorker extends Worker {
    private static final String UNIQUE_WORK = "little-orbit-location";
    public static final String ACTION_COLLECTION_DISABLED =
            "com.littleorbit.action.LOCATION_COLLECTION_DISABLED";
    private final LocationSampler sampler;

    /** Creates the fallback worker around the shared privacy-gated sampler. */
    @AssistedInject
    public LocationCollectionWorker(@Assisted @NonNull Context context,
            @Assisted @NonNull WorkerParameters parameters, LocationSampler sampler) {
        super(context, parameters);
        this.sampler = sampler;
    }

    /** Samples once; permission or consent removal stops retries. */
    @NonNull
    @Override
    public Result doWork() {
        return switch (sampler.collect(false)) {
            case COLLECTED -> Result.success();
            case TEMPORARY_FAILURE -> Result.retry();
            case DISABLED -> Result.failure();
        };
    }

    /** Reconciles the unique fifteen-minute fallback with current server consent. */
    public static void schedule(Context context, boolean enabled) {
        WorkManager work = WorkManager.getInstance(context);
        if (!enabled) {
            work.cancelUniqueWork(UNIQUE_WORK);
            context.sendBroadcast(new android.content.Intent(ACTION_COLLECTION_DISABLED)
                    .setPackage(context.getPackageName()));
            return;
        }
        PeriodicWorkRequest request = new PeriodicWorkRequest.Builder(
                LocationCollectionWorker.class, 15, TimeUnit.MINUTES)
                .build();
        work.enqueueUniquePeriodicWork(
                UNIQUE_WORK, ExistingPeriodicWorkPolicy.UPDATE, request);
    }
}
