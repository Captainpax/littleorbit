package com.littleorbit.data.repository;

import android.content.Context;
import androidx.work.ExistingPeriodicWorkPolicy;
import androidx.work.PeriodicWorkRequest;
import androidx.work.WorkManager;
import com.littleorbit.data.LocationCollectionWorker;
import com.littleorbit.data.WearCachePublisher;
import com.littleorbit.data.local.DisplayCacheDao;
import com.littleorbit.data.local.DisplayCacheEntity;
import com.littleorbit.data.local.LocationQueueDao;
import com.littleorbit.data.remote.ApiModels;
import com.littleorbit.data.remote.LittleOrbitApi;
import com.littleorbit.data.security.SessionStore;
import java.io.IOException;
import java.time.Instant;
import java.util.List;
import java.util.Map;
import java.util.concurrent.CompletableFuture;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import java.util.concurrent.TimeUnit;
import java.util.concurrent.atomic.AtomicInteger;
import dagger.hilt.android.qualifiers.ApplicationContext;
import javax.inject.Inject;
import javax.inject.Singleton;
import retrofit2.Call;
import retrofit2.Response;

/** Bounded Retrofit repository with no Android UI behavior. */
@Singleton
public final class NetworkOrbitRepository implements OrbitRepository {
    private final AtomicInteger threadIds = new AtomicInteger();
    private final LittleOrbitApi api;
    private final SessionStore sessions;
    private final DisplayCacheDao displayCache;
    private final LocationQueueDao locationQueue;
    private final WearCachePublisher wearPublisher;
    private final CountdownOfflineStore offlineCountdowns;
    private final WorkManager workManager;
    private final ExecutorService executor = Executors.newFixedThreadPool(3, runnable -> {
        Thread thread = new Thread(runnable, "orbit-network-" + threadIds.incrementAndGet());
        thread.setDaemon(true);
        return thread;
    });

    /** Creates the authenticated network and cache boundary. */
    @Inject
    public NetworkOrbitRepository(
            LittleOrbitApi api,
            SessionStore sessions,
            DisplayCacheDao displayCache,
            LocationQueueDao locationQueue,
            WearCachePublisher wearPublisher,
            CountdownOfflineStore offlineCountdowns,
            @ApplicationContext Context context) {
        this.api = api;
        this.sessions = sessions;
        this.displayCache = displayCache;
        this.locationQueue = locationQueue;
        this.wearPublisher = wearPublisher;
        this.offlineCountdowns = offlineCountdowns;
        this.workManager = WorkManager.getInstance(context);
    }

    @Override
    public boolean isSignedIn() {
        return sessions.read().isPresent();
    }

    @Override
    public CompletableFuture<ApiModels.SessionResponse> signIn(String email, String password) {
        return async(api.login(new ApiModels.LoginRequest(email, password)))
                .thenApply(session -> {
                    sessions.save(session.accessToken);
                    return session;
                });
    }

    @Override
    public CompletableFuture<Void> signOut() {
        if (!isSignedIn()) {
            disableLocationWork();
            offlineCountdowns.clear();
            sessions.clear();
            return CompletableFuture.completedFuture(null);
        }
        return async(api.logout()).handle((ignored, failure) -> {
            disableLocationWork();
            offlineCountdowns.clear();
            sessions.clear();
            return null;
        });
    }

    @Override
    public CompletableFuture<Void> refreshHome() {
        return CompletableFuture.supplyAsync(() -> {
            ApiModels.TogetherSummary summary = execute(api.togetherSummary());
            List<ApiModels.Countdown> countdowns = execute(api.countdowns());
            ApiModels.Countdown next = countdowns.stream()
                    .filter(item -> Instant.parse(item.occursAt).isAfter(Instant.now()))
                    .min((left, right) -> left.occursAt.compareTo(right.occursAt))
                    .orElse(null);
            DisplayCacheEntity cache = new DisplayCacheEntity(
                    "primary",
                    summary.estimatedSeconds,
                    next == null ? "No countdown yet" : next.title,
                    next == null ? 0 : Instant.parse(next.occursAt).toEpochMilli(),
                    Instant.now().toEpochMilli());
            displayCache.replace(cache);
            wearPublisher.publish(cache);
            return null;
        }, executor);
    }

    @Override
    public CompletableFuture<ApiModels.PairCodeResponse> createPairCode() {
        return async(api.createPairCode());
    }

    @Override
    public CompletableFuture<ApiModels.PairingState> redeemPairCode(String code) {
        return async(api.redeemPairCode(new ApiModels.PairRedeemRequest(code)));
    }

    @Override
    public CompletableFuture<ApiModels.PendingPairing> pendingPairing() {
        return async(api.pendingPairing());
    }

    @Override
    public CompletableFuture<ApiModels.PairingState> confirmPairing(String requestId) {
        return async(api.confirmPairing(new ApiModels.PairConfirmRequest(requestId)));
    }

    @Override
    public CompletableFuture<List<ApiModels.Question>> dailyQuestions(String localDate) {
        return async(api.dailyQuestions(localDate));
    }

    @Override
    public CompletableFuture<List<ApiModels.Question>> submitAnswer(
            String questionId, ApiModels.AnswerRequest answer) {
        return async(api.submitAnswer(questionId, answer));
    }

    @Override
    public CompletableFuture<ApiModels.Question> createCustomQuestion(
            ApiModels.CustomQuestionRequest request) {
        return async(api.createCustomQuestion(request));
    }

    @Override
    public CompletableFuture<ApiModels.Message> reportQuestion(
            String questionId, ApiModels.QuestionReportRequest request) {
        return async(api.reportQuestion(questionId, request));
    }

    @Override
    public CompletableFuture<List<ApiModels.Countdown>> countdowns() {
        return CompletableFuture.supplyAsync(() -> {
            try {
                List<ApiModels.Countdown> remote = execute(api.countdowns());
                offlineCountdowns.replaceRemote(remote);
                return offlineCountdowns.cached();
            } catch (OrbitServiceException failure) {
                if (failure.statusCode() != -1) {
                    throw failure;
                }
                return offlineCountdowns.cached();
            }
        }, executor);
    }

    @Override
    public CompletableFuture<ApiModels.Countdown> createCountdown(
            ApiModels.CountdownMutation mutation) {
        return CompletableFuture.supplyAsync(() -> createCountdownOrQueue(mutation), executor);
    }

    @Override
    public CompletableFuture<ApiModels.Countdown> updateCountdown(
            String countdownId, ApiModels.CountdownMutation mutation) {
        return CompletableFuture.supplyAsync(
                () -> updateCountdownOrQueue(countdownId, mutation), executor);
    }

    @Override
    public CompletableFuture<ApiModels.Message> deleteCountdown(
            String countdownId, ApiModels.CountdownDeleteRequest request) {
        return CompletableFuture.supplyAsync(
                () -> deleteCountdownOrQueue(countdownId, request), executor);
    }

    @Override
    public CompletableFuture<ApiModels.TogetherSummary> togetherSummary() {
        return async(api.togetherSummary());
    }

    @Override
    public CompletableFuture<List<ApiModels.TogetherBucket>> togetherBuckets() {
        return async(api.togetherBuckets());
    }

    @Override
    public CompletableFuture<ApiModels.TogetherSummary> correctTogetherBucket(
            String bucketId, ApiModels.TogetherCorrectionRequest request) {
        return async(api.correctTogetherBucket(bucketId, request));
    }

    @Override
    public CompletableFuture<List<ApiModels.Note>> notes() {
        return async(api.notes());
    }

    @Override
    public CompletableFuture<ApiModels.Note> createNote(ApiModels.NoteCreateRequest request) {
        return async(api.createNote(request));
    }

    @Override
    public CompletableFuture<ApiModels.Preferences> preferences() {
        return async(api.preferences());
    }

    @Override
    public CompletableFuture<ApiModels.Preferences> updatePreferences(
            ApiModels.PreferencesMutation mutation) {
        return async(api.updatePreferences(mutation)).thenApply(result -> {
            configureLocationWork(result.locationByMe);
            return result;
        });
    }

    @Override
    public CompletableFuture<ApiModels.UnpairResult> unpair() {
        return async(api.unpair()).thenApply(result -> {
            disableLocationWork();
            return result;
        });
    }

    @Override
    public CompletableFuture<List<ApiModels.ArchiveSummary>> archives() {
        return async(api.archives());
    }

    @Override
    public CompletableFuture<ApiModels.ArchiveDetail> archive(String archiveId) {
        return async(api.archive(archiveId));
    }

    @Override
    public CompletableFuture<Map<String, Object>> exportAccount() {
        return async(api.exportAccount());
    }

    @Override
    public CompletableFuture<ApiModels.DeletionResult> deleteAccount(String password) {
        return async(api.deleteAccount(new ApiModels.DeletionRequest(password)))
                .thenApply(result -> {
                    disableLocationWork();
                    offlineCountdowns.clear();
                    sessions.clear();
                    return result;
                });
    }

    private void configureLocationWork(boolean enabled) {
        if (!enabled) {
            disableLocationWork();
            return;
        }
        PeriodicWorkRequest request =
                new PeriodicWorkRequest.Builder(LocationCollectionWorker.class, 15, TimeUnit.MINUTES)
                        .build();
        workManager.enqueueUniquePeriodicWork(
                "little-orbit-location", ExistingPeriodicWorkPolicy.UPDATE, request);
    }

    private void disableLocationWork() {
        workManager.cancelUniqueWork("little-orbit-location");
        locationQueue.clear();
    }

    private ApiModels.Countdown createCountdownOrQueue(ApiModels.CountdownMutation mutation) {
        try {
            return execute(api.createCountdown(mutation));
        } catch (OrbitServiceException failure) {
            if (failure.statusCode() == -1) {
                return offlineCountdowns.queueCreate(mutation);
            }
            throw failure;
        }
    }

    private ApiModels.Countdown updateCountdownOrQueue(
            String countdownId, ApiModels.CountdownMutation mutation) {
        if (countdownId.startsWith("local:")) {
            return offlineCountdowns.queueUpdate(countdownId, mutation);
        }
        try {
            return execute(api.updateCountdown(countdownId, mutation));
        } catch (OrbitServiceException failure) {
            if (failure.statusCode() == -1) {
                return offlineCountdowns.queueUpdate(countdownId, mutation);
            }
            throw failure;
        }
    }

    private ApiModels.Message deleteCountdownOrQueue(
            String countdownId, ApiModels.CountdownDeleteRequest request) {
        if (countdownId.startsWith("local:")) {
            return offlineCountdowns.queueDelete(countdownId, request);
        }
        try {
            return execute(api.deleteCountdown(countdownId, request));
        } catch (OrbitServiceException failure) {
            if (failure.statusCode() == -1) {
                return offlineCountdowns.queueDelete(countdownId, request);
            }
            throw failure;
        }
    }

    private <T> CompletableFuture<T> async(Call<T> call) {
        return CompletableFuture.supplyAsync(() -> execute(call), executor);
    }

    private static <T> T execute(Call<T> call) {
        try {
            Response<T> response = call.execute();
            T body = response.body();
            if (!response.isSuccessful() || body == null) {
                throw new OrbitServiceException(response.code());
            }
            return body;
        } catch (IOException exception) {
            throw new OrbitServiceException(exception);
        }
    }

    /** Stable error that never includes response bodies or credentials. */
    public static final class OrbitServiceException extends RuntimeException {
        private final int statusCode;

        /** Creates an HTTP-status failure. */
        public OrbitServiceException(int statusCode) {
            super("Little Orbit request failed with status " + statusCode);
            this.statusCode = statusCode;
        }

        /** Creates a transport failure without secret-bearing request data. */
        public OrbitServiceException(IOException cause) {
            super("Little Orbit could not reach the server", cause);
            this.statusCode = -1;
        }

        /** Returns the HTTP status, or -1 for a transport failure. */
        public int statusCode() {
            return statusCode;
        }
    }
}
