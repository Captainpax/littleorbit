package com.littleorbit.data.repository;

import android.content.Context;
import com.littleorbit.data.LocationCollectionWorker;
import com.littleorbit.data.DisplayCacheSynchronizer;
import com.littleorbit.data.DisplayCacheSyncWorker;
import com.littleorbit.data.local.LocationQueueDao;
import com.littleorbit.data.remote.ApiModels;
import com.littleorbit.data.remote.NoteApiModels;
import com.littleorbit.data.remote.LittleOrbitApi;
import com.littleorbit.data.remote.QuizApiModels;
import com.littleorbit.data.remote.SmoochApiModels;
import com.littleorbit.data.remote.TogetherTimeModels;
import com.littleorbit.data.security.SessionStore;
import java.io.IOException;
import java.util.List;
import java.util.Map;
import java.util.concurrent.CompletableFuture;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
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
    private final LocationQueueDao locationQueue;
    private final DisplayCacheSynchronizer displaySynchronizer;
    private final Context context;
    private final CountdownOfflineStore offlineCountdowns;
    private final ProfileRepository profiles;
    private final SmoochOutbox smoochOutbox;
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
            LocationQueueDao locationQueue,
            DisplayCacheSynchronizer displaySynchronizer,
            CountdownOfflineStore offlineCountdowns,
            ProfileRepository profiles,
            SmoochOutbox smoochOutbox,
            @ApplicationContext Context context) {
        this.api = api;
        this.sessions = sessions;
        this.locationQueue = locationQueue;
        this.displaySynchronizer = displaySynchronizer;
        this.context = context;
        this.offlineCountdowns = offlineCountdowns;
        this.profiles = profiles;
        this.smoochOutbox = smoochOutbox;
    }

    @Override
    public boolean isSignedIn() {
        return sessions.read().isPresent();
    }

    @Override
    public CompletableFuture<ApiModels.SessionResponse> signIn(String email, String password) {
        return async(api.login(new ApiModels.LoginRequest(email, password)))
                .thenApply(session -> {
                    clearRelationshipState();
                    profiles.clearAll();
                    sessions.save(session.accessToken);
                    DisplayCacheSyncWorker.schedule(context);
                    DisplayCacheSyncWorker.enqueue(context);
                    return session;
                });
    }

    @Override
    public CompletableFuture<Void> signOut() {
        if (!isSignedIn()) {
            return CompletableFuture.runAsync(this::clearLocalSession, executor);
        }
        return async(api.logout()).handle((ignored, failure) -> {
            clearLocalSession();
            return null;
        });
    }

    @Override
    public CompletableFuture<Void> refreshHome() {
        return CompletableFuture.supplyAsync(() -> {
            try {
                displaySynchronizer.refresh();
                DisplayCacheSyncWorker.schedule(context);
            } catch (DisplayCacheSynchronizer.SyncException failure) {
                throw new OrbitServiceException(failure.statusCode());
            }
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
    public CompletableFuture<QuizApiModels.Day> quizToday() {
        return async(api.quizToday());
    }

    @Override
    public CompletableFuture<QuizApiModels.Day> quizDay(String quizDate) {
        return async(api.quizDay(quizDate));
    }

    @Override
    public CompletableFuture<List<QuizApiModels.HistoryItem>> quizHistory() {
        return async(api.quizHistory(30));
    }

    @Override
    public CompletableFuture<QuizApiModels.Status> quizStatus() {
        return async(api.quizStatus());
    }

    @Override
    public CompletableFuture<QuizApiModels.Day> saveQuizDraft(
            String quizDate, String questionId, QuizApiModels.DraftMutation mutation) {
        return async(api.saveQuizDraft(quizDate, questionId, mutation));
    }

    @Override
    public CompletableFuture<QuizApiModels.Day> finishQuiz(
            String quizDate, QuizApiModels.DayMutation mutation) {
        return async(api.finishQuiz(quizDate, mutation));
    }

    @Override
    public CompletableFuture<QuizApiModels.Day> reopenQuiz(
            String quizDate, QuizApiModels.DayMutation mutation) {
        return async(api.reopenQuiz(quizDate, mutation));
    }

    @Override
    public CompletableFuture<QuizApiModels.CustomQueue> customQuizQueue() {
        return async(api.customQuizQueue());
    }

    @Override
    public CompletableFuture<QuizApiModels.CustomQuestion> createCustomQuiz(
            QuizApiModels.CustomMutation mutation) {
        return async(api.createCustomQuiz(mutation));
    }

    @Override
    public CompletableFuture<ApiModels.Message> reportQuizQuestion(
            String questionId, QuizApiModels.ReportMutation mutation) {
        return async(api.reportQuizQuestion(questionId, mutation));
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
    public CompletableFuture<TogetherTimeModels.Summary> togetherSummaryV2() {
        return async(api.togetherSummaryV2());
    }

    @Override
    public CompletableFuture<TogetherTimeModels.PairSummary> togetherSummaryV3() {
        return async(api.togetherSummaryV3());
    }

    @Override
    public CompletableFuture<SmoochApiModels.Sent> sendSmooch(
            SmoochApiModels.SendRequest request) {
        return async(api.sendSmooch(request));
    }

    @Override
    public CompletableFuture<List<SmoochApiModels.Delivery>> pendingSmooches() {
        return async(api.pendingSmooches());
    }

    @Override
    public CompletableFuture<Void> acknowledgeSmooches(List<String> ids) {
        return CompletableFuture.runAsync(
                () -> executeVoid(api.acknowledgeSmooches(new SmoochApiModels.DeliveryAck(ids))),
                executor);
    }

    @Override
    public CompletableFuture<List<SmoochApiModels.Week>> smoochWeeks(int weeks) {
        return async(api.smoochWeeks(weeks));
    }

    @Override
    public CompletableFuture<List<TogetherTimeModels.HistoryDay>> togetherHistory() {
        return async(api.togetherHistory(30));
    }

    @Override
    public CompletableFuture<TogetherTimeModels.StartDateProposal> proposeStartDate(
            TogetherTimeModels.ProposalRequest request) {
        return async(api.proposeStartDate(request)).thenApply(result -> {
            DisplayCacheSyncWorker.enqueue(context);
            return result;
        });
    }

    @Override
    public CompletableFuture<TogetherTimeModels.StartDateProposal> decideStartDate(
            String proposalId, TogetherTimeModels.DecisionRequest request) {
        return async(api.decideStartDate(proposalId, request)).thenApply(result -> {
            DisplayCacheSyncWorker.enqueue(context);
            return result;
        });
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
    public CompletableFuture<List<NoteApiModels.Note>> notes() {
        return async(api.notes());
    }

    @Override
    public CompletableFuture<NoteApiModels.Note> createNote(NoteApiModels.CreateRequest request) {
        return async(api.createNote(request));
    }

    @Override
    public CompletableFuture<List<NoteApiModels.Note>> archivedNotes() {
        return async(api.archivedNotes());
    }

    @Override
    public CompletableFuture<NoteApiModels.Note> renameNote(
            String noteId, NoteApiModels.TitleRequest request) {
        return async(api.renameNote(noteId, request));
    }

    @Override
    public CompletableFuture<NoteApiModels.Note> archiveNote(
            String noteId, NoteApiModels.ArchiveRequest request) {
        return async(api.archiveNote(noteId, request));
    }

    @Override
    public CompletableFuture<NoteApiModels.Note> restoreNote(
            String noteId, NoteApiModels.ArchiveRequest request) {
        return async(api.restoreNote(noteId, request));
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
            clearRelationshipState();
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
                    clearLocalSession();
                    return result;
                });
    }

    private void clearLocalSession() {
        clearRelationshipState();
        profiles.clearAll();
        sessions.clear();
    }

    private void clearRelationshipState() {
        disableLocationWork();
        offlineCountdowns.clear();
        DisplayCacheSyncWorker.cancel(context);
        displaySynchronizer.clear();
        profiles.clearPartner();
        smoochOutbox.clear();
    }

    private void configureLocationWork(boolean enabled) {
        if (!enabled) {
            disableLocationWork();
            return;
        }
        LocationCollectionWorker.schedule(context, true);
    }

    private void disableLocationWork() {
        LocationCollectionWorker.schedule(context, false);
        locationQueue.clear();
    }

    private ApiModels.Countdown createCountdownOrQueue(ApiModels.CountdownMutation mutation) {
        try {
            ApiModels.Countdown result = execute(api.createCountdown(mutation));
            DisplayCacheSyncWorker.enqueue(context);
            return result;
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
            ApiModels.Countdown result = execute(api.updateCountdown(countdownId, mutation));
            DisplayCacheSyncWorker.enqueue(context);
            return result;
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
            ApiModels.Message result = execute(api.deleteCountdown(countdownId, request));
            DisplayCacheSyncWorker.enqueue(context);
            return result;
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

    private static void executeVoid(Call<Void> call) {
        try {
            Response<Void> response = call.execute();
            if (!response.isSuccessful()) throw new OrbitServiceException(response.code());
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
