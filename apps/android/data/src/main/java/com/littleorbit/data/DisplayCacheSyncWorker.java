package com.littleorbit.data;

import android.content.Context;
import androidx.annotation.NonNull;
import androidx.hilt.work.HiltWorker;
import androidx.work.Constraints;
import androidx.work.ExistingPeriodicWorkPolicy;
import androidx.work.NetworkType;
import androidx.work.OneTimeWorkRequest;
import androidx.work.PeriodicWorkRequest;
import androidx.work.WorkManager;
import androidx.work.Worker;
import androidx.work.WorkerParameters;
import com.littleorbit.data.security.SessionStore;
import com.littleorbit.data.repository.ProfileRepository;
import dagger.assisted.Assisted;
import dagger.assisted.AssistedInject;
import java.util.concurrent.TimeUnit;

/** Bounded signed-in refresh for phone, widget, and watch display state. */
@HiltWorker
public final class DisplayCacheSyncWorker extends Worker {
    private static final String PERIODIC_NAME = "little-orbit-display-cache";
    private final DisplayCacheSynchronizer synchronizer;
    private final SessionStore sessions;
    private final ProfileRepository profiles;

    /** Creates an injected display refresh worker. */
    @AssistedInject
    public DisplayCacheSyncWorker(
            @Assisted @NonNull Context context,
            @Assisted @NonNull WorkerParameters parameters,
            DisplayCacheSynchronizer synchronizer,
            SessionStore sessions,
            ProfileRepository profiles) {
        super(context, parameters);
        this.synchronizer = synchronizer;
        this.sessions = sessions;
        this.profiles = profiles;
    }

    @NonNull
    @Override
    public Result doWork() {
        if (sessions.read().isEmpty()) {
            synchronizer.clear();
            return Result.success();
        }
        try {
            synchronizer.refresh();
            return Result.success();
        } catch (DisplayCacheSynchronizer.SyncException failure) {
            int code = failure.statusCode();
            if (code == 401) {
                profiles.clearAll();
                sessions.clear();
                synchronizer.clear();
                return Result.success();
            }
            return code == -1 || code >= 500 ? Result.retry() : Result.failure();
        }
    }

    /** Starts a unique immediate refresh after a user-visible state change. */
    public static void enqueue(Context context) {
        WorkManager.getInstance(context).enqueueUniqueWork(
                "little-orbit-display-cache-now",
                androidx.work.ExistingWorkPolicy.REPLACE,
                new OneTimeWorkRequest.Builder(DisplayCacheSyncWorker.class)
                        .setConstraints(networkConstraints())
                        .build());
    }

    /** Keeps cache recency bounded while an authenticated session exists. */
    public static void schedule(Context context) {
        PeriodicWorkRequest request = new PeriodicWorkRequest.Builder(
                DisplayCacheSyncWorker.class, 6, TimeUnit.HOURS)
                .setConstraints(networkConstraints())
                .build();
        WorkManager.getInstance(context).enqueueUniquePeriodicWork(
                PERIODIC_NAME, ExistingPeriodicWorkPolicy.UPDATE, request);
    }

    /** Stops refresh work as soon as local account context is cleared. */
    public static void cancel(Context context) {
        WorkManager manager = WorkManager.getInstance(context);
        manager.cancelUniqueWork(PERIODIC_NAME);
        manager.cancelUniqueWork("little-orbit-display-cache-now");
    }

    private static Constraints networkConstraints() {
        return new Constraints.Builder()
                .setRequiredNetworkType(NetworkType.CONNECTED)
                .build();
    }
}
