package com.littleorbit.data;

import android.Manifest;
import android.content.Context;
import android.content.pm.PackageManager;
import android.location.Location;
import androidx.annotation.NonNull;
import androidx.core.content.ContextCompat;
import androidx.hilt.work.HiltWorker;
import androidx.work.OneTimeWorkRequest;
import androidx.work.WorkManager;
import androidx.work.Worker;
import androidx.work.WorkerParameters;
import com.google.android.gms.location.LocationServices;
import com.google.android.gms.location.Priority;
import com.google.android.gms.tasks.CancellationTokenSource;
import com.google.android.gms.tasks.Tasks;
import com.littleorbit.data.local.LocationQueueDao;
import com.littleorbit.data.local.QueuedLocationEntity;
import com.littleorbit.data.remote.ApiModels;
import com.littleorbit.data.remote.LittleOrbitApi;
import com.littleorbit.data.security.SessionStore;
import dagger.assisted.Assisted;
import dagger.assisted.AssistedInject;
import java.time.Instant;
import java.util.UUID;
import java.util.concurrent.TimeUnit;
import org.json.JSONException;
import org.json.JSONObject;
import retrofit2.Response;

/** Collects one balanced-power location only after local and server consent checks. */
@HiltWorker
public final class LocationCollectionWorker extends Worker {
    private final Context context;
    private final LocationQueueDao queue;
    private final SessionStore cipher;
    private final LittleOrbitApi api;

    /** Creates an injected privacy-gated collection worker. */
    @AssistedInject
    public LocationCollectionWorker(
            @Assisted @NonNull Context context,
            @Assisted @NonNull WorkerParameters parameters,
            LocationQueueDao queue,
            SessionStore cipher,
            LittleOrbitApi api) {
        super(context, parameters);
        this.context = context;
        this.queue = queue;
        this.cipher = cipher;
        this.api = api;
    }

    /** Verifies consent, encrypts one sample, and schedules upload. */
    @NonNull
    @Override
    public Result doWork() {
        if (!hasLocationPermissions()) {
            queue.clear();
            return Result.failure();
        }
        if (serverConsentDenied()) {
            queue.clear();
            return Result.failure();
        }
        try {
            Location location = Tasks.await(
                    LocationServices.getFusedLocationProviderClient(context).getCurrentLocation(
                            Priority.PRIORITY_BALANCED_POWER_ACCURACY,
                            new CancellationTokenSource().getToken()),
                    20,
                    TimeUnit.SECONDS);
            if (location == null || !location.hasAccuracy() || location.getAccuracy() > 1000) {
                return Result.retry();
            }
            enqueue(location);
            WorkManager.getInstance(context).enqueue(
                    new OneTimeWorkRequest.Builder(LocationUploadWorker.class).build());
            return Result.success();
        } catch (SecurityException exception) {
            queue.clear();
            return Result.failure();
        } catch (Exception exception) {
            return Result.retry();
        }
    }

    private boolean serverConsentDenied() {
        try {
            Response<ApiModels.Preferences> response = api.preferences().execute();
            if (response.isSuccessful() && response.body() != null) {
                return !response.body().locationByMe;
            }
            return response.code() >= 400 && response.code() < 500;
        } catch (java.io.IOException offline) {
            // Local opt-in and encryption allow collection while temporarily offline.
            return false;
        }
    }

    private boolean hasLocationPermissions() {
        return ContextCompat.checkSelfPermission(context, Manifest.permission.ACCESS_FINE_LOCATION)
                        == PackageManager.PERMISSION_GRANTED
                && ContextCompat.checkSelfPermission(
                                context, Manifest.permission.ACCESS_BACKGROUND_LOCATION)
                        == PackageManager.PERMISSION_GRANTED;
    }

    private void enqueue(Location location) throws JSONException {
        String sampleId = UUID.randomUUID().toString();
        long recordedAt = System.currentTimeMillis();
        JSONObject payload = new JSONObject()
                .put("recorded_at", Instant.ofEpochMilli(recordedAt).toString())
                .put("latitude", location.getLatitude())
                .put("longitude", location.getLongitude())
                .put("accuracy_m", location.getAccuracy());
        queue.insert(new QueuedLocationEntity(
                sampleId, cipher.seal(payload.toString()), recordedAt));
    }
}
