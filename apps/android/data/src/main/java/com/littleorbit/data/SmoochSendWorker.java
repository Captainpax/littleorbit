package com.littleorbit.data;

import android.content.Context;
import androidx.annotation.NonNull;
import androidx.hilt.work.HiltWorker;
import androidx.work.Constraints;
import androidx.work.ExistingWorkPolicy;
import androidx.work.NetworkType;
import androidx.work.OneTimeWorkRequest;
import androidx.work.WorkManager;
import androidx.work.Worker;
import androidx.work.WorkerParameters;
import com.littleorbit.data.remote.SmoochApiModels;
import com.littleorbit.data.repository.OrbitServiceException;
import com.littleorbit.data.repository.OrbitRepository;
import com.littleorbit.data.repository.SmoochOutbox;
import dagger.assisted.Assisted;
import dagger.assisted.AssistedInject;
import java.util.concurrent.ExecutionException;
import java.util.concurrent.TimeUnit;

/** Flushes short-lived offline Smooches without delivering stale affection hours later. */
@HiltWorker
public final class SmoochSendWorker extends Worker {
    private final OrbitRepository orbit;
    private final SmoochOutbox outbox;

    /** Creates the retry worker. */
    @AssistedInject
    public SmoochSendWorker(@Assisted @NonNull Context context,
            @Assisted @NonNull WorkerParameters parameters, OrbitRepository orbit,
            SmoochOutbox outbox) {
        super(context, parameters);
        this.orbit = orbit;
        this.outbox = outbox;
    }

    @NonNull
    @Override
    public Result doWork() {
        boolean retry = false;
        for (SmoochOutbox.Pending item : outbox.pending(System.currentTimeMillis())) {
            try {
                orbit.sendSmooch(new SmoochApiModels.SendRequest(
                                item.operationId(), item.emoji()))
                        .get(30, TimeUnit.SECONDS);
                outbox.remove(item.operationId());
            } catch (Exception failure) {
                int code = statusCode(failure);
                if (code == -1 || code == 429 || code >= 500) retry = true;
                else outbox.remove(item.operationId());
            }
        }
        return retry && !outbox.pending(System.currentTimeMillis()).isEmpty()
                ? Result.retry() : Result.success();
    }

    /** Enqueues one network-constrained flush, replacing only an idle prior request. */
    public static void enqueue(Context context) {
        Constraints constraints = new Constraints.Builder()
                .setRequiredNetworkType(NetworkType.CONNECTED)
                .build();
        OneTimeWorkRequest request = new OneTimeWorkRequest.Builder(SmoochSendWorker.class)
                .setConstraints(constraints)
                .build();
        WorkManager.getInstance(context).enqueueUniqueWork(
                "little-orbit-smooch-outbox", ExistingWorkPolicy.KEEP, request);
    }

    private static int statusCode(Exception failure) {
        Throwable current = failure;
        while (current instanceof ExecutionException && current.getCause() != null) {
            current = current.getCause();
        }
        if (current instanceof OrbitServiceException service) {
            return service.statusCode();
        }
        return -1;
    }
}
