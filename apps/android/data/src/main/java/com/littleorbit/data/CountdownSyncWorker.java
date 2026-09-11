package com.littleorbit.data;

import android.content.Context;
import androidx.annotation.NonNull;
import androidx.hilt.work.HiltWorker;
import androidx.work.Worker;
import androidx.work.WorkerParameters;
import com.littleorbit.data.local.CountdownDao;
import com.littleorbit.data.local.QueuedCountdownEntity;
import com.littleorbit.data.remote.ApiModels;
import com.littleorbit.data.remote.LittleOrbitApi;
import com.littleorbit.data.repository.CountdownOfflineStore;
import dagger.assisted.Assisted;
import dagger.assisted.AssistedInject;
import java.io.IOException;
import org.json.JSONException;
import org.json.JSONObject;
import retrofit2.Response;

/** Replays encrypted countdown mutations in creation order once connectivity returns. */
@HiltWorker
public final class CountdownSyncWorker extends Worker {
    private final CountdownDao queue;
    private final CountdownOfflineStore offline;
    private final LittleOrbitApi api;

    /** Creates an injected bounded synchronization worker. */
    @AssistedInject
    public CountdownSyncWorker(
            @Assisted @NonNull Context context,
            @Assisted @NonNull WorkerParameters parameters,
            CountdownDao queue,
            CountdownOfflineStore offline,
            LittleOrbitApi api) {
        super(context, parameters);
        this.queue = queue;
        this.offline = offline;
        this.api = api;
    }

    /** Replays up to twenty operations and stops at the first retryable failure. */
    @NonNull
    @Override
    public Result doWork() {
        for (QueuedCountdownEntity row : queue.queued()) {
            SyncOutcome outcome = synchronize(row);
            if (outcome == SyncOutcome.RETRY) {
                return Result.retry();
            }
            if (outcome == SyncOutcome.AUTHORIZATION_FAILURE) {
                return Result.failure();
            }
        }
        return Result.success();
    }

    private SyncOutcome synchronize(QueuedCountdownEntity row) {
        JSONObject payload = offline.queuedPayload(row).orElse(null);
        if (payload == null) {
            return SyncOutcome.ACKNOWLEDGED;
        }
        try {
            return interpret(row, execute(row, payload));
        } catch (IOException exception) {
            return SyncOutcome.RETRY;
        } catch (JSONException exception) {
            offline.markConflict(row);
            return SyncOutcome.CONFLICT;
        }
    }

    private Response<?> execute(QueuedCountdownEntity row, JSONObject payload)
            throws IOException, JSONException {
        if ("create".equals(row.kind)) {
            return api.createCountdown(mutation(row, payload)).execute();
        }
        if ("update".equals(row.kind) && row.countdownId != null) {
            return api.updateCountdown(row.countdownId, mutation(row, payload)).execute();
        }
        if ("delete".equals(row.kind) && row.countdownId != null) {
            ApiModels.CountdownDeleteRequest request = new ApiModels.CountdownDeleteRequest(
                    row.operationId, payload.getInt("expected_revision"));
            return api.deleteCountdown(row.countdownId, request).execute();
        }
        throw new JSONException("unknown queued countdown operation");
    }

    private SyncOutcome interpret(QueuedCountdownEntity row, Response<?> response) {
        if (response.isSuccessful()) {
            ApiModels.Countdown countdown = response.body() instanceof ApiModels.Countdown
                    ? (ApiModels.Countdown) response.body()
                    : null;
            offline.acknowledge(row, countdown);
            return SyncOutcome.ACKNOWLEDGED;
        }
        if (response.code() == 401 || response.code() == 403) {
            return SyncOutcome.AUTHORIZATION_FAILURE;
        }
        if (response.code() >= 400 && response.code() < 500) {
            offline.markConflict(row);
            return SyncOutcome.CONFLICT;
        }
        return SyncOutcome.RETRY;
    }

    private static ApiModels.CountdownMutation mutation(
            QueuedCountdownEntity row, JSONObject payload) throws JSONException {
        Integer expected = payload.isNull("expected_revision")
                ? null
                : payload.getInt("expected_revision");
        return new ApiModels.CountdownMutation(
                row.operationId,
                payload.getString("title"),
                payload.getString("occurs_at"),
                payload.getString("timezone"),
                payload.getString("notes"),
                expected);
    }

    private enum SyncOutcome {
        ACKNOWLEDGED,
        CONFLICT,
        RETRY,
        AUTHORIZATION_FAILURE
    }
}
