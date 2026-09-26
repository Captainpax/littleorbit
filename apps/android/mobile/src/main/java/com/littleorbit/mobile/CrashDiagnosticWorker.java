package com.littleorbit.mobile;

import android.content.Context;
import androidx.annotation.NonNull;
import androidx.hilt.work.HiltWorker;
import androidx.work.BackoffPolicy;
import androidx.work.Constraints;
import androidx.work.ExistingWorkPolicy;
import androidx.work.NetworkType;
import androidx.work.OneTimeWorkRequest;
import androidx.work.WorkManager;
import androidx.work.Worker;
import androidx.work.WorkerParameters;
import com.littleorbit.data.remote.DiagnosticApiModels;
import com.littleorbit.data.repository.OrbitServiceException;
import com.littleorbit.data.repository.OrbitRepository;
import dagger.assisted.Assisted;
import dagger.assisted.AssistedInject;
import java.util.concurrent.ExecutionException;
import java.util.concurrent.TimeUnit;

/** Delivers one pending, explicitly enabled crash report over the authenticated API. */
@HiltWorker
public final class CrashDiagnosticWorker extends Worker {
    private static final String UNIQUE = "little-orbit-content-free-crash";
    private final OrbitRepository orbit;
    private final NotificationDeviceStore device;
    private final CrashDiagnosticStore store;

    /** Creates the bounded background diagnostic delivery worker. */
    @AssistedInject
    public CrashDiagnosticWorker(
            @Assisted @NonNull Context context,
            @Assisted @NonNull WorkerParameters parameters,
            OrbitRepository orbit,
            NotificationDeviceStore device,
            CrashDiagnosticStore store) {
        super(context, parameters);
        this.orbit = orbit;
        this.device = device;
        this.store = store;
    }

    @NonNull
    @Override
    public Result doWork() {
        if (!store.enabled() || !orbit.isSignedIn()) return Result.success();
        DiagnosticApiModels.Report report = store.load(device.id());
        if (report == null) return Result.success();
        try {
            orbit.reportCrash(report).get(30, TimeUnit.SECONDS);
            store.clearIfCurrent(report.occurredAt);
            return Result.success();
        } catch (Exception failure) {
            if (terminal(failure)) store.clearIfCurrent(report.occurredAt);
            return retryable(failure) && getRunAttemptCount() < 3
                    ? Result.retry() : Result.failure();
        }
    }

    /** Requests delivery on the next connected period without uploading automatically on crash. */
    public static void enqueue(Context context) {
        Constraints network = new Constraints.Builder()
                .setRequiredNetworkType(NetworkType.CONNECTED).build();
        OneTimeWorkRequest request = new OneTimeWorkRequest.Builder(CrashDiagnosticWorker.class)
                .setConstraints(network)
                .setBackoffCriteria(BackoffPolicy.EXPONENTIAL, 30, TimeUnit.SECONDS)
                .build();
        WorkManager.getInstance(context).enqueueUniqueWork(UNIQUE, ExistingWorkPolicy.KEEP, request);
    }

    /** Cancels pending transmission after sign-out, unpair, deletion, or suspension. */
    public static void cancel(Context context) {
        WorkManager.getInstance(context).cancelUniqueWork(UNIQUE);
    }

    private static boolean terminal(Exception failure) {
        OrbitServiceException service = serviceFailure(failure);
        return service != null && service.statusCode() >= 400 && service.statusCode() < 500;
    }

    private static boolean retryable(Exception failure) {
        OrbitServiceException service = serviceFailure(failure);
        return service == null || service.statusCode() < 0 || service.statusCode() >= 500;
    }

    private static OrbitServiceException serviceFailure(Exception failure) {
        Throwable value = failure instanceof ExecutionException ? failure.getCause() : failure;
        return value instanceof OrbitServiceException service ? service : null;
    }
}
