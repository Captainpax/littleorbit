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
import com.littleorbit.data.repository.SafeServiceError;
import com.littleorbit.data.security.SessionStore;
import dagger.assisted.Assisted;
import dagger.assisted.AssistedInject;
import java.io.IOException;
import java.util.ArrayList;
import java.util.List;
import org.json.JSONException;
import org.json.JSONObject;
import retrofit2.Response;

/** Uploads only Keystore-decrypted samples from the current relationship generation. */
@HiltWorker
public final class LocationUploadWorker extends Worker {
    private static final long MAX_QUEUE_AGE_MILLIS = 23L * 60 * 60 * 1000 + 45L * 60 * 1000;
    private final LocationQueueDao queue;
    private final SessionStore cipher;
    private final LittleOrbitApi api;
    private final DisplayCacheSynchronizer displaySynchronizer;
    private final RelationshipDisplayIdentity relationshipIdentity;

    /** Creates an injected bounded upload worker. */
    @AssistedInject
    public LocationUploadWorker(
            @Assisted @NonNull Context context,
            @Assisted @NonNull WorkerParameters parameters,
            LocationQueueDao queue,
            SessionStore cipher,
            LittleOrbitApi api,
            DisplayCacheSynchronizer displaySynchronizer,
            RelationshipDisplayIdentity relationshipIdentity) {
        super(context, parameters);
        this.queue = queue;
        this.cipher = cipher;
        this.api = api;
        this.displaySynchronizer = displaySynchronizer;
        this.relationshipIdentity = relationshipIdentity;
    }

    /** Uploads a maximum of 48 samples and deletes only acknowledged or invalid rows. */
    @NonNull
    @Override
    public Result doWork() {
        RelationshipDisplayIdentity.Snapshot relationship = relationshipIdentity.read();
        if (!relationship.active()) {
            queue.clear();
            return Result.success();
        }
        prepareQueue(relationship);
        DecodedBatch batch = decode(queue.oldestBatch(
                relationship.relationshipId(), relationship.generation()));
        if (batch.samples().isEmpty()) return Result.success();
        try {
            return handleBatch(relationship, batch);
        } catch (IOException unavailable) {
            return Result.retry();
        }
    }

    private void prepareQueue(RelationshipDisplayIdentity.Snapshot relationship) {
        queue.deleteOlderThan(System.currentTimeMillis() - MAX_QUEUE_AGE_MILLIS);
        queue.deleteOutsideRelationship(
                relationship.relationshipId(), relationship.generation());
    }

    private Result handleBatch(RelationshipDisplayIdentity.Snapshot relationship,
            DecodedBatch batch) throws IOException {
        Response<TogetherTimeModels.LocationBatchResult> response = upload(
                relationship.relationshipId(), batch.samples());
        if (!relationshipIdentity.read().equals(relationship)) {
            queue.deleteByIds(ids(batch.rows()));
            return Result.success();
        }
        if (response.isSuccessful()) {
            acknowledge(batch.rows());
            return Result.success();
        }
        if (invalidatesRelationship(response)) return purgeAndFail();
        if (response.code() == 400 || response.code() == 409 || response.code() == 422) {
            return isolateInvalidRows(relationship, batch);
        }
        return response.code() == 429 || response.code() >= 500
                ? Result.retry() : Result.failure();
    }

    private Result isolateInvalidRows(RelationshipDisplayIdentity.Snapshot relationship,
            DecodedBatch batch) throws IOException {
        boolean acknowledged = false;
        for (int index = 0; index < batch.rows().size(); index++) {
            if (!relationshipIdentity.read().equals(relationship)) return Result.success();
            Response<TogetherTimeModels.LocationBatchResult> response = upload(
                    relationship.relationshipId(), List.of(batch.samples().get(index)));
            if (response.isSuccessful()) {
                queue.deleteByIds(List.of(batch.rows().get(index).sampleId));
                acknowledged = true;
            } else if (invalidatesRelationship(response)) {
                return purgeAndFail();
            } else if (response.code() == 400 || response.code() == 409
                    || response.code() == 422) {
                queue.deleteByIds(List.of(batch.rows().get(index).sampleId));
            } else if (response.code() == 429 || response.code() >= 500) {
                if (acknowledged) refreshDisplayCache();
                return Result.retry();
            } else {
                return Result.failure();
            }
        }
        if (acknowledged) refreshDisplayCache();
        return Result.success();
    }

    private Response<TogetherTimeModels.LocationBatchResult> upload(
            String relationshipId, List<ApiModels.LocationSample> samples) throws IOException {
        return api.uploadLocations(
                new TogetherTimeModels.LocationBatch(relationshipId, samples)).execute();
    }

    private static boolean invalidatesRelationship(Response<?> response) {
        return response.code() == 401 || response.code() == 403
                || SafeServiceError.relationshipInactive(response);
    }

    private Result purgeAndFail() {
        queue.clear();
        displaySynchronizer.clear();
        return Result.failure();
    }

    private void acknowledge(List<QueuedLocationEntity> rows) {
        queue.deleteByIds(ids(rows));
        refreshDisplayCache();
    }

    private void refreshDisplayCache() {
        try {
            displaySynchronizer.refresh();
        } catch (DisplayCacheSynchronizer.SyncException ignored) {
            // An acknowledged location batch must not be retried just for passive display refresh.
        }
    }

    private DecodedBatch decode(List<QueuedLocationEntity> rows) {
        List<QueuedLocationEntity> validRows = new ArrayList<>(rows.size());
        List<ApiModels.LocationSample> samples = new ArrayList<>(rows.size());
        for (QueuedLocationEntity row : rows) {
            ApiModels.LocationSample sample = decode(row);
            if (sample == null) queue.deleteByIds(List.of(row.sampleId));
            else {
                validRows.add(row);
                samples.add(sample);
            }
        }
        return new DecodedBatch(List.copyOf(validRows), List.copyOf(samples));
    }

    private ApiModels.LocationSample decode(QueuedLocationEntity row) {
        String plaintext = cipher.open(row.encryptedPayload).orElse(null);
        if (plaintext == null) return null;
        try {
            JSONObject item = new JSONObject(plaintext);
            return new ApiModels.LocationSample(
                    row.sampleId,
                    item.getString("recorded_at"),
                    item.getDouble("latitude"),
                    item.getDouble("longitude"),
                    item.getDouble("accuracy_m"));
        } catch (JSONException invalid) {
            return null;
        }
    }

    private static List<String> ids(List<QueuedLocationEntity> rows) {
        List<String> values = new ArrayList<>(rows.size());
        for (QueuedLocationEntity row : rows) values.add(row.sampleId);
        return values;
    }

    private record DecodedBatch(
            List<QueuedLocationEntity> rows, List<ApiModels.LocationSample> samples) {}
}
