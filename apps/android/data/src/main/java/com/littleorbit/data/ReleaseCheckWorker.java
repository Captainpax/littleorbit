package com.littleorbit.data;

import android.content.Context;
import androidx.annotation.NonNull;
import androidx.hilt.work.HiltWorker;
import androidx.work.Constraints;
import androidx.work.ExistingPeriodicWorkPolicy;
import androidx.work.NetworkType;
import androidx.work.PeriodicWorkRequest;
import androidx.work.WorkManager;
import androidx.work.Worker;
import androidx.work.WorkerParameters;
import com.littleorbit.data.repository.ReleaseRepository;
import dagger.assisted.Assisted;
import dagger.assisted.AssistedInject;
import java.util.concurrent.TimeUnit;

/** Daily metadata-only update check; APK bytes are never downloaded here. */
@HiltWorker
public final class ReleaseCheckWorker extends Worker {
    private final ReleaseRepository releases;

    /** Creates the bounded background metadata check. */
    @AssistedInject
    public ReleaseCheckWorker(
            @Assisted @NonNull Context context,
            @Assisted @NonNull WorkerParameters parameters,
            ReleaseRepository releases) {
        super(context, parameters);
        this.releases = releases;
    }

    @NonNull
    @Override
    public Result doWork() {
        try {
            releases.refresh().get(30, TimeUnit.SECONDS);
            return Result.success();
        } catch (Exception unavailable) {
            return getRunAttemptCount() < 3 ? Result.retry() : Result.failure();
        }
    }

    /** Schedules one network-constrained check per day without replacing active work. */
    public static void schedule(Context context) {
        Constraints constraints = new Constraints.Builder()
                .setRequiredNetworkType(NetworkType.CONNECTED)
                .build();
        PeriodicWorkRequest request = new PeriodicWorkRequest.Builder(
                ReleaseCheckWorker.class, 24, TimeUnit.HOURS)
                .setConstraints(constraints)
                .build();
        WorkManager.getInstance(context).enqueueUniquePeriodicWork(
                "little-orbit-release-check", ExistingPeriodicWorkPolicy.UPDATE, request);
    }
}
