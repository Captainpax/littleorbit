package com.littleorbit.data;

import android.content.Context;
import androidx.annotation.NonNull;
import androidx.hilt.work.HiltWorker;
import androidx.work.Worker;
import androidx.work.WorkerParameters;
import com.littleorbit.data.local.LocationQueueDao;
import com.littleorbit.data.local.QueuedLocationEntity;
import com.littleorbit.data.remote.ApiModels;
import com.littleorbit.data.remote.LittleOrbitApi;
import com.littleorbit.data.remote.TogetherTimeModels;
import com.littleorbit.data.security.SessionStore;
import dagger.assisted.Assisted;
import dagger.assisted.AssistedInject;
import java.util.ArrayList;
import java.util.List;
import org.json.JSONException;
import org.json.JSONObject;
import retrofit2.Response;

/** Uploads only Keystore-decrypted, consented location batches. */
@HiltWorker
public final class LocationUploadWorker extends Worker {
    private final LocationQueueDao queue;
    private final SessionStore cipher;
    private final LittleOrbitApi api;
    private final DisplayCacheSynchronizer displaySynchronizer;

    /** Creates an injected bounded upload worker. */
    @AssistedInject
    public LocationUploadWorker(
            @Assisted @NonNull Context context,
            @Assisted @NonNull WorkerParameters parameters,
            LocationQueueDao queue,
            SessionStore cipher,
            LittleOrbitApi api,
            DisplayCacheSynchronizer displaySynchronizer) {
        super(context, parameters);
        this.queue = queue;
        this.cipher = cipher;
        this.api = api;
        this.displaySynchronizer = displaySynchronizer;
    }

    /** Uploads a maximum of 48 samples and deletes only acknowledged rows. */
    @NonNull
    @Override
    public Result doWork() {
        queue.deleteOlderThan(System.currentTimeMillis() - 24L * 60 * 60 * 1000);
        List<QueuedLocationEntity> rows = queue.oldestBatch();
        if (rows.isEmpty()) {
            return Result.success();
        }
        try {
            List<ApiModels.LocationSample> samples = decode(rows);
            if (samples.isEmpty()) {
                return Result.success();
            }
            Response<TogetherTimeModels.LocationBatchResult> response =
                    api.uploadLocations(new ApiModels.LocationBatch(samples)).execute();
            if (response.isSuccessful()) {
                List<String> ids = new ArrayList<>(rows.size());
                for (QueuedLocationEntity row : rows) {
                    ids.add(row.sampleId);
                }
                queue.deleteByIds(ids);
                refreshDisplayCache();
                return Result.success();
            }
            if (response.code() == 403) {
                queue.clear();
                return Result.failure();
            }
            return response.code() >= 500 ? Result.retry() : Result.failure();
        } catch (java.io.IOException exception) {
            return Result.retry();
        }
    }

    private void refreshDisplayCache() {
        try {
            displaySynchronizer.refresh();
        } catch (DisplayCacheSynchronizer.SyncException ignored) {
            // The acknowledged location batch must not be retried just for display refresh.
        }
    }

    private List<ApiModels.LocationSample> decode(List<QueuedLocationEntity> rows) {
        List<ApiModels.LocationSample> samples = new ArrayList<>(rows.size());
        for (QueuedLocationEntity row : rows) {
            String plaintext = cipher.open(row.encryptedPayload).orElse(null);
            if (plaintext == null) {
                queue.deleteByIds(List.of(row.sampleId));
                continue;
            }
            try {
                JSONObject item = new JSONObject(plaintext);
                samples.add(new ApiModels.LocationSample(
                        row.sampleId,
                        item.getString("recorded_at"),
                        item.getDouble("latitude"),
                        item.getDouble("longitude"),
                        item.getDouble("accuracy_m")));
            } catch (JSONException exception) {
                queue.deleteByIds(List.of(row.sampleId));
            }
        }
        return samples;
    }
}
