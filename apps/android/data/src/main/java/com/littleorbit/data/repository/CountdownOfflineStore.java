package com.littleorbit.data.repository;

import android.content.Context;
import androidx.work.Constraints;
import androidx.work.ExistingWorkPolicy;
import androidx.work.NetworkType;
import androidx.work.OneTimeWorkRequest;
import androidx.work.WorkManager;
import com.littleorbit.data.CountdownSyncWorker;
import com.littleorbit.data.local.CountdownCacheEntity;
import com.littleorbit.data.local.CountdownDao;
import com.littleorbit.data.local.QueuedCountdownEntity;
import com.littleorbit.data.remote.ApiModels;
import com.littleorbit.data.security.SessionStore;
import dagger.hilt.android.qualifiers.ApplicationContext;
import java.time.Instant;
import java.util.ArrayList;
import java.util.List;
import javax.inject.Inject;
import javax.inject.Singleton;
import org.json.JSONException;
import org.json.JSONObject;

/** Owns encrypted countdown snapshots and disconnected mutation queuing. */
@Singleton
public final class CountdownOfflineStore {
    private final CountdownDao dao;
    private final SessionStore cipher;
    private final WorkManager workManager;

    /** Creates the private offline boundary. */
    @Inject
    public CountdownOfflineStore(
            CountdownDao dao, SessionStore cipher, @ApplicationContext Context context) {
        this.dao = dao;
        this.cipher = cipher;
        this.workManager = WorkManager.getInstance(context);
    }

    /** Replaces confirmed snapshots while preserving local edits and conflicts. */
    public void replaceRemote(List<ApiModels.Countdown> countdowns) {
        List<CountdownCacheEntity> rows = new ArrayList<>(countdowns.size());
        for (ApiModels.Countdown item : countdowns) {
            rows.add(cacheRow(item, false, false));
        }
        dao.replaceRemote(rows);
    }

    /** Returns every decryptable local snapshot. */
    public List<ApiModels.Countdown> cached() {
        List<ApiModels.Countdown> result = new ArrayList<>();
        for (CountdownCacheEntity row : dao.cached()) {
            decode(row).ifPresent(result::add);
        }
        return result;
    }

    /** Queues a disconnected create and returns its visible optimistic state. */
    public ApiModels.Countdown queueCreate(ApiModels.CountdownMutation mutation) {
        String localId = "local:" + mutation.operationId;
        ApiModels.Countdown optimistic = optimistic(localId, mutation);
        cacheAndQueue(optimistic, "create", null, mutation.operationId, mutationJson(mutation));
        return optimistic;
    }

    /** Queues a disconnected update from the exact optimistic revision. */
    public ApiModels.Countdown queueUpdate(
            String countdownId, ApiModels.CountdownMutation mutation) {
        if (countdownId.startsWith("local:")) {
            return updateLocalCreate(countdownId, mutation);
        }
        ApiModels.Countdown optimistic = optimistic(countdownId, mutation);
        cacheAndQueue(
                optimistic, "update", countdownId, mutation.operationId, mutationJson(mutation));
        return optimistic;
    }

    /** Queues a disconnected delete and removes its local display snapshot. */
    public ApiModels.Message queueDelete(
            String countdownId, ApiModels.CountdownDeleteRequest request) {
        if (countdownId.startsWith("local:")) {
            dao.deleteQueued(countdownId.substring("local:".length()));
            dao.deleteCache(countdownId);
            return new ApiModels.Message("Unsent countdown removed.");
        }
        JSONObject payload = jsonObject("expected_revision", request.expectedRevision);
        enqueue("delete", countdownId, request.operationId, payload);
        dao.deleteCache(countdownId);
        return new ApiModels.Message("Countdown deletion queued for sync.");
    }

    private ApiModels.Countdown updateLocalCreate(
            String countdownId, ApiModels.CountdownMutation mutation) {
        String originalOperationId = countdownId.substring("local:".length());
        ApiModels.CountdownMutation folded = new ApiModels.CountdownMutation(
                originalOperationId,
                mutation.title,
                mutation.occursAt,
                mutation.timezone,
                mutation.notes,
                null);
        ApiModels.Countdown optimistic = optimistic(countdownId, folded);
        dao.upsertCache(cacheRow(optimistic, true, false));
        dao.updateQueuedCreate(
                originalOperationId, cipher.seal(mutationJson(folded).toString()));
        return optimistic;
    }

    /** Clears all relationship content and pending work after sign-out or deletion. */
    public void clear() {
        workManager.cancelUniqueWork("little-orbit-countdown-sync");
        dao.clearQueue();
        dao.clearCache();
    }

    /** Returns a decrypted queued payload or empty after key invalidation. */
    public java.util.Optional<JSONObject> queuedPayload(QueuedCountdownEntity row) {
        try {
            String plaintext = cipher.open(row.encryptedPayload).orElseThrow();
            return java.util.Optional.of(new JSONObject(plaintext));
        } catch (JSONException | java.util.NoSuchElementException exception) {
            dao.deleteQueued(row.operationId);
            return java.util.Optional.empty();
        }
    }

    /** Applies one server acknowledgement to the queue and encrypted cache. */
    public void acknowledge(QueuedCountdownEntity row, ApiModels.Countdown response) {
        dao.deleteQueued(row.operationId);
        if ("create".equals(row.kind)) {
            dao.deleteCache("local:" + row.operationId);
        }
        if (response != null) {
            dao.upsertCache(cacheRow(response, false, false));
        }
    }

    /** Retains the optimistic version and exposes a resolvable conflict marker. */
    public void markConflict(QueuedCountdownEntity row) {
        dao.deleteQueued(row.operationId);
        String cacheId = row.countdownId == null ? "local:" + row.operationId : row.countdownId;
        dao.markConflict(cacheId);
    }

    private void cacheAndQueue(
            ApiModels.Countdown item,
            String kind,
            String countdownId,
            String operationId,
            JSONObject payload) {
        dao.upsertCache(cacheRow(item, true, false));
        enqueue(kind, countdownId, operationId, payload);
    }

    private void enqueue(
            String kind, String countdownId, String operationId, JSONObject payload) {
        dao.enqueue(new QueuedCountdownEntity(
                operationId,
                kind,
                countdownId,
                cipher.seal(payload.toString()),
                System.currentTimeMillis()));
        Constraints connected = new Constraints.Builder()
                .setRequiredNetworkType(NetworkType.CONNECTED)
                .build();
        OneTimeWorkRequest request = new OneTimeWorkRequest.Builder(CountdownSyncWorker.class)
                .setConstraints(connected)
                .build();
        workManager.enqueueUniqueWork(
                "little-orbit-countdown-sync", ExistingWorkPolicy.KEEP, request);
    }

    private CountdownCacheEntity cacheRow(
            ApiModels.Countdown item, boolean pending, boolean conflict) {
        return new CountdownCacheEntity(
                item.id,
                cipher.seal(countdownJson(item).toString()),
                Instant.parse(item.occursAt).toEpochMilli(),
                pending,
                conflict);
    }

    private java.util.Optional<ApiModels.Countdown> decode(CountdownCacheEntity row) {
        try {
            String plaintext = cipher.open(row.encryptedPayload).orElseThrow();
            JSONObject item = new JSONObject(plaintext);
            return java.util.Optional.of(new ApiModels.Countdown(
                    row.countdownId,
                    item.getString("title"),
                    item.getString("occurs_at"),
                    item.getString("timezone"),
                    item.getString("notes"),
                    item.getInt("revision"),
                    item.getString("updated_at"),
                    row.pendingSync,
                    row.syncConflict));
        } catch (JSONException | java.util.NoSuchElementException exception) {
            dao.deleteCache(row.countdownId);
            return java.util.Optional.empty();
        }
    }

    private static ApiModels.Countdown optimistic(
            String countdownId, ApiModels.CountdownMutation mutation) {
        int revision = mutation.expectedRevision == null ? 0 : mutation.expectedRevision + 1;
        return new ApiModels.Countdown(
                countdownId,
                mutation.title,
                mutation.occursAt,
                mutation.timezone,
                mutation.notes,
                revision,
                Instant.now().toString(),
                true,
                false);
    }

    private static JSONObject mutationJson(ApiModels.CountdownMutation mutation) {
        JSONObject result = countdownFields(
                mutation.title, mutation.occursAt, mutation.timezone, mutation.notes);
        put(result, "expected_revision", mutation.expectedRevision);
        return result;
    }

    private static JSONObject countdownJson(ApiModels.Countdown item) {
        JSONObject result = countdownFields(item.title, item.occursAt, item.timezone, item.notes);
        put(result, "revision", item.revision);
        put(result, "updated_at", item.updatedAt);
        return result;
    }

    private static JSONObject countdownFields(
            String title, String occursAt, String timezone, String notes) {
        return jsonObject(
                "title", title,
                "occurs_at", occursAt,
                "timezone", timezone,
                "notes", notes);
    }

    private static JSONObject jsonObject(Object... pairs) {
        JSONObject result = new JSONObject();
        for (int index = 0; index < pairs.length; index += 2) {
            put(result, String.valueOf(pairs[index]), pairs[index + 1]);
        }
        return result;
    }

    private static void put(JSONObject target, String key, Object value) {
        try {
            target.put(key, value);
        } catch (JSONException impossible) {
            throw new IllegalStateException("Countdown JSON encoding failed", impossible);
        }
    }
}
