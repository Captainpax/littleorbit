package com.littleorbit.data.repository;

import android.content.Context;
import com.littleorbit.data.LocationCollectionWorker;
import com.littleorbit.data.DisplayCacheSynchronizer;
import com.littleorbit.data.DisplayCacheSyncWorker;
import com.littleorbit.data.local.LocationQueueDao;
import com.littleorbit.data.remote.ApiModels;
import com.littleorbit.data.remote.CountdownApiModels;
import com.littleorbit.data.remote.DiagnosticApiModels;
import com.littleorbit.data.remote.ActivityApiModels;
import com.littleorbit.data.remote.NoteApiModels;
import com.littleorbit.data.remote.NotificationApiModels;
import com.littleorbit.data.remote.LittleOrbitApi;
import com.littleorbit.data.remote.QuizApiModels;
import com.littleorbit.data.remote.SmoochApiModels;
import com.littleorbit.data.remote.TogetherTimeModels;
import com.littleorbit.data.security.SessionStore;
import java.io.File;
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

/** Bounded Retrofit repository with no Android UI behavior. */
@Singleton
public final class NetworkOrbitRepository implements OrbitRepository {
    private final AtomicInteger threadIds = new AtomicInteger();
    private final LittleOrbitApi api;
    private final SessionStore sessions;
    private final LocationQueueDao locationQueue;
    private final DisplayCacheSynchronizer displaySynchronizer;
    private final Context context;
    private final CountdownSyncGateway countdownGateway;
    private final ProfileRepository profiles;
    private final SmoochOutbox smoochOutbox;
    private final NoteDraftStore noteDrafts;
    private final NoteAttachmentTransfer attachments;
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
            NoteDraftStore noteDrafts,
            @ApplicationContext Context context) {
        this.api = api;
        this.sessions = sessions;
        this.locationQueue = locationQueue;
        this.displaySynchronizer = displaySynchronizer;
        this.context = context;
        this.countdownGateway = new CountdownSyncGateway(api, offlineCountdowns, context);
        this.profiles = profiles;
        this.smoochOutbox = smoochOutbox;
        this.noteDrafts = noteDrafts;
        this.attachments = new NoteAttachmentTransfer(api, context);
    }

    @Override public boolean isSignedIn() { return sessions.read().isPresent(); }

    @Override
    public CompletableFuture<ApiModels.SessionResponse> signIn(String email, String password) {
        return rawAsync(api.login(new ApiModels.LoginRequest(email, password)))
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
        return rawAsync(api.logout()).handle((ignored, failure) -> {
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
                if (failure.statusCode() == 401) clearLocalSession();
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
    public CompletableFuture<List<CountdownApiModels.Countdown>> countdowns() {
        return purge(CompletableFuture.supplyAsync(countdownGateway::load, executor));
    }

    @Override
    public CompletableFuture<CountdownApiModels.Countdown> createCountdown(
            CountdownApiModels.Mutation mutation) {
        return purge(CompletableFuture.supplyAsync(
                () -> countdownGateway.create(mutation), executor));
    }

    @Override
    public CompletableFuture<CountdownApiModels.Countdown> updateCountdown(
            String countdownId, CountdownApiModels.Mutation mutation) {
        return purge(CompletableFuture.supplyAsync(
                () -> countdownGateway.update(countdownId, mutation), executor));
    }

    @Override
    public CompletableFuture<ApiModels.Message> deleteCountdown(
            String countdownId, CountdownApiModels.DeleteRequest request) {
        return purge(CompletableFuture.supplyAsync(
                () -> countdownGateway.delete(countdownId, request), executor));
    }

    @Override public CompletableFuture<ApiModels.Message> reportCrash(
            DiagnosticApiModels.Report report) { return async(api.reportCrash(report)); }

    @Override
    public CompletableFuture<CountdownApiModels.Countdown> replaceCountdownReminders(
            String countdownId, List<Integer> offsetsMinutes) {
        return async(api.replaceCountdownReminders(
                countdownId, new CountdownApiModels.ReminderUpdate(offsetsMinutes)));
    }

    @Override public CompletableFuture<ActivityApiModels.Page> activity() { return async(api.activity(null, 30, false)); }

    @Override
    public CompletableFuture<Void> markActivitySeen(long throughSequence, String operationId) {
        return purge(CompletableFuture.runAsync(() -> RetrofitCalls.executeVoid(api.markActivitySeen(
                new ActivityApiModels.SeenRequest(throughSequence, operationId))), executor));
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
    public CompletableFuture<SmoochApiModels.Status> smoochStatus() {
        return async(api.smoochStatus());
    }

    @Override
    public CompletableFuture<List<SmoochApiModels.Delivery>> pendingSmooches() {
        return async(api.pendingSmooches());
    }

    @Override
    public CompletableFuture<Void> acknowledgeSmooches(List<String> ids) {
        return purge(CompletableFuture.runAsync(
                () -> RetrofitCalls.executeVoid(
                        api.acknowledgeSmooches(new SmoochApiModels.DeliveryAck(ids))),
                executor));
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
    public CompletableFuture<TogetherTimeModels.HistoryDay> correctTogetherDay(
            String day, TogetherTimeModels.DayCorrection request) {
        return async(api.correctTogetherDay(day, request));
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

    @Override public CompletableFuture<List<NoteApiModels.Note>> notes() { return async(api.notes()); }

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
    public CompletableFuture<NotificationApiModels.Preferences> notificationPreferences() {
        return async(api.notificationPreferences());
    }

    @Override
    public CompletableFuture<NotificationApiModels.Preferences> updateNotificationPreferences(
            NotificationApiModels.PreferencesUpdate request) {
        return async(api.updateNotificationPreferences(request));
    }

    @Override
    public CompletableFuture<NotificationApiModels.Device> registerNotificationDevice(
            String deviceId, NotificationApiModels.DeviceUpsert request) {
        return async(api.registerNotificationDevice(deviceId, request));
    }

    @Override
    public CompletableFuture<Void> disableNotificationDevice(String deviceId) {
        return purge(CompletableFuture.runAsync(
                () -> RetrofitCalls.executeVoid(api.disableNotificationDevice(deviceId)), executor));
    }

    @Override
    public CompletableFuture<List<NotificationApiModels.Event>> pendingNotifications(
            String deviceId) {
        return async(api.pendingNotifications(deviceId));
    }

    @Override
    public CompletableFuture<Void> acknowledgeNotifications(
            String deviceId, List<String> eventIds) {
        return purge(CompletableFuture.runAsync(
                () -> RetrofitCalls.executeVoid(api.acknowledgeNotifications(
                        new NotificationApiModels.DeliveryAck(deviceId, eventIds))), executor));
    }

    @Override
    public CompletableFuture<List<NoteApiModels.Attachment>> noteAttachments(String noteId) {
        return async(api.noteAttachments(noteId));
    }

    @Override
    public CompletableFuture<NoteApiModels.Attachment> uploadNoteAttachment(
            String noteId, String displayName, String mediaType, File file) {
        return purge(CompletableFuture.supplyAsync(
                () -> attachments.upload(noteId, displayName, mediaType, file), executor));
    }

    @Override
    public CompletableFuture<File> downloadNoteAttachment(
            String noteId, NoteApiModels.Attachment attachment) {
        return purge(CompletableFuture.supplyAsync(
                () -> attachments.download(noteId, attachment), executor));
    }

    @Override
    public CompletableFuture<Void> deleteNoteAttachment(String noteId, String attachmentId) {
        return purge(CompletableFuture.runAsync(() -> {
            RetrofitCalls.executeVoid(api.deleteNoteAttachment(noteId, attachmentId));
            attachments.evict(attachmentId);
        }, executor));
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
        return async(api.unpair()).whenComplete((result, failure) -> {
            if (result != null || RelationshipCachePurger.relationshipInactive(failure)) {
                clearRelationshipState();
            }
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
    public CompletableFuture<List<NoteApiModels.Attachment>> archiveAttachments(
            String archiveId, String noteId) {
        return async(api.archiveAttachments(archiveId, noteId));
    }

    @Override
    public CompletableFuture<File> downloadArchiveAttachment(
            String archiveId, String noteId, NoteApiModels.Attachment attachment) {
        return CompletableFuture.supplyAsync(
                () -> attachments.downloadArchive(archiveId, noteId, attachment), executor);
    }

    @Override
    public CompletableFuture<Map<String, Object>> exportAccount() {
        return async(api.exportAccount());
    }

    @Override
    public CompletableFuture<ApiModels.DeletionResult> deleteAccount(String password) {
        return rawAsync(api.deleteAccount(new ApiModels.DeletionRequest(password)))
                .thenApply(result -> {
                    clearLocalSession();
                    return result;
                });
    }

    private void clearLocalSession() {
        try {
            clearRelationshipState();
            profiles.clearAll();
        } finally {
            sessions.clear();
        }
    }

    private void clearRelationshipState() {
        disableLocationWork();
        countdownGateway.clear();
        DisplayCacheSyncWorker.cancel(context);
        displaySynchronizer.clear();
        profiles.clearPartner();
        smoochOutbox.clear();
        noteDrafts.clearAll();
        RelationshipCachePurger.clearFiles(context);
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

    private <T> CompletableFuture<T> async(Call<T> call) {
        CompletableFuture<T> request = rawAsync(call);
        return RelationshipCachePurger.purgeAccountWhenSessionInvalid(
                purge(request), this::clearLocalSession);
    }

    private <T> CompletableFuture<T> rawAsync(Call<T> call) {
        return CompletableFuture.supplyAsync(() -> RetrofitCalls.execute(call), executor);
    }

    private <T> CompletableFuture<T> purge(CompletableFuture<T> request) {
        return RelationshipCachePurger.purgeWhenInactive(request, this::clearRelationshipState);
    }

}
