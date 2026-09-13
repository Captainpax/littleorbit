package com.littleorbit.data;

import android.Manifest;
import android.content.Context;
import android.content.pm.PackageManager;
import android.location.Location;
import androidx.core.content.ContextCompat;
import androidx.work.OneTimeWorkRequest;
import androidx.work.WorkManager;
import com.google.android.gms.location.LocationServices;
import com.google.android.gms.location.Priority;
import com.google.android.gms.tasks.CancellationTokenSource;
import com.google.android.gms.tasks.Tasks;
import com.littleorbit.data.local.LocationQueueDao;
import com.littleorbit.data.local.QueuedLocationEntity;
import com.littleorbit.data.remote.ApiModels;
import com.littleorbit.data.remote.LittleOrbitApi;
import com.littleorbit.data.security.SessionStore;
import dagger.hilt.android.qualifiers.ApplicationContext;
import java.io.IOException;
import java.time.Instant;
import java.util.UUID;
import java.util.concurrent.TimeUnit;
import javax.inject.Inject;
import javax.inject.Singleton;
import org.json.JSONObject;
import retrofit2.Response;

/** Privacy-gated reusable sampler for foreground tracking and WorkManager fallback. */
@Singleton
public final class LocationSampler {
    /** Sanitized result used to stop immediately when permission or consent disappears. */
    public enum Outcome { COLLECTED, TEMPORARY_FAILURE, DISABLED }

    private final Context context;
    private final LocationQueueDao queue;
    private final SessionStore cipher;
    private final LittleOrbitApi api;

    /** Creates a sampler whose queued coordinates are always Keystore encrypted. */
    @Inject
    public LocationSampler(@ApplicationContext Context context, LocationQueueDao queue,
            SessionStore cipher, LittleOrbitApi api) {
        this.context = context;
        this.queue = queue;
        this.cipher = cipher;
        this.api = api;
    }

    /** Collects one sample at the requested fused-location priority. */
    public Outcome collect(boolean highAccuracy) {
        if (!hasPermissions() || serverConsentDenied()) {
            queue.clear();
            return Outcome.DISABLED;
        }
        try {
            int priority = highAccuracy
                    ? Priority.PRIORITY_HIGH_ACCURACY
                    : Priority.PRIORITY_BALANCED_POWER_ACCURACY;
            Location location = Tasks.await(
                    LocationServices.getFusedLocationProviderClient(context).getCurrentLocation(
                            priority, new CancellationTokenSource().getToken()),
                    25,
                    TimeUnit.SECONDS);
            if (!usable(location)) return Outcome.TEMPORARY_FAILURE;
            enqueue(location);
            WorkManager.getInstance(context).enqueue(
                    new OneTimeWorkRequest.Builder(LocationUploadWorker.class).build());
            return Outcome.COLLECTED;
        } catch (SecurityException denied) {
            queue.clear();
            return Outcome.DISABLED;
        } catch (Exception unavailable) {
            return Outcome.TEMPORARY_FAILURE;
        }
    }

    private boolean serverConsentDenied() {
        try {
            Response<ApiModels.Preferences> response = api.preferences().execute();
            if (response.isSuccessful() && response.body() != null) {
                return !response.body().locationByBoth;
            }
            return response.code() >= 400 && response.code() < 500;
        } catch (IOException offline) {
            return false;
        }
    }

    private boolean hasPermissions() {
        return ContextCompat.checkSelfPermission(context, Manifest.permission.ACCESS_FINE_LOCATION)
                        == PackageManager.PERMISSION_GRANTED
                && ContextCompat.checkSelfPermission(
                                context, Manifest.permission.ACCESS_BACKGROUND_LOCATION)
                        == PackageManager.PERMISSION_GRANTED;
    }

    private void enqueue(Location location) throws Exception {
        long recordedAt = location.getTime();
        JSONObject payload = new JSONObject()
                .put("recorded_at", Instant.ofEpochMilli(recordedAt).toString())
                .put("latitude", location.getLatitude())
                .put("longitude", location.getLongitude())
                .put("accuracy_m", location.getAccuracy());
        queue.insert(new QueuedLocationEntity(
                UUID.randomUUID().toString(), cipher.seal(payload.toString()), recordedAt));
        queue.trimToLimit();
    }

    private static boolean usable(Location location) {
        if (location == null || !location.hasAccuracy() || location.getAccuracy() > 200) {
            return false;
        }
        long ageMillis = System.currentTimeMillis() - location.getTime();
        return ageMillis >= 0 && ageMillis <= TimeUnit.MINUTES.toMillis(2);
    }
}
