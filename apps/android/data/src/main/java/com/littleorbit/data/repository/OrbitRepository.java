package com.littleorbit.data.repository;

import com.littleorbit.data.remote.ApiModels;
import com.littleorbit.data.remote.CountdownApiModels;
import com.littleorbit.data.remote.ActivityApiModels;
import com.littleorbit.data.remote.NoteApiModels;
import com.littleorbit.data.remote.NotificationApiModels;
import com.littleorbit.data.remote.QuizApiModels;
import com.littleorbit.data.remote.SmoochApiModels;
import com.littleorbit.data.remote.TogetherTimeModels;
import java.util.List;
import java.util.Map;
import java.io.File;
import java.util.concurrent.CompletableFuture;

/** Authenticated application boundary used by Android presentation code. */
public interface OrbitRepository {
    /** Returns whether an encrypted local session is available. */
    boolean isSignedIn();

    /** Authenticates and persists the returned opaque session. */
    CompletableFuture<ApiModels.SessionResponse> signIn(String email, String password);

    /** Revokes the server session and clears the local token. */
    CompletableFuture<Void> signOut();

    /** Refreshes together-time and next-countdown display cache. */
    CompletableFuture<Void> refreshHome();

    /** Creates a pair code. */
    CompletableFuture<ApiModels.PairCodeResponse> createPairCode();

    /** Redeems a partner's pair code. */
    CompletableFuture<ApiModels.PairingState> redeemPairCode(String code);

    /** Loads creator confirmation metadata. */
    CompletableFuture<ApiModels.PendingPairing> pendingPairing();

    /** Confirms a reserved pairing. */
    CompletableFuture<ApiModels.PairingState> confirmPairing(String requestId);

    /** Loads daily questions. */
    CompletableFuture<List<ApiModels.Question>> dailyQuestions(String localDate);

    /** Submits one typed answer. */
    CompletableFuture<List<ApiModels.Question>> submitAnswer(
            String questionId, ApiModels.AnswerRequest answer);

    /** Creates a custom question for the active couple. */
    CompletableFuture<ApiModels.Question> createCustomQuestion(
            ApiModels.CustomQuestionRequest request);

    /** Immediately hides and reports a question. */
    CompletableFuture<ApiModels.Message> reportQuestion(
            String questionId, ApiModels.QuestionReportRequest request);

    /** Loads today's shared UTC quiz state. */
    CompletableFuture<QuizApiModels.Day> quizToday();

    /** Loads one current or historical UTC quiz state. */
    CompletableFuture<QuizApiModels.Day> quizDay(String quizDate);

    /** Loads thirty days of quiz navigation state. */
    CompletableFuture<List<QuizApiModels.HistoryItem>> quizHistory();

    /** Loads content-free quiz state for delayed background notifications. */
    CompletableFuture<QuizApiModels.Status> quizStatus();

    /** Saves one revisioned private quiz draft. */
    CompletableFuture<QuizApiModels.Day> saveQuizDraft(
            String quizDate, String questionId, QuizApiModels.DraftMutation mutation);

    /** Marks the caller's reviewed quiz complete. */
    CompletableFuture<QuizApiModels.Day> finishQuiz(
            String quizDate, QuizApiModels.DayMutation mutation);

    /** Reopens a finished quiz before shared reveal. */
    CompletableFuture<QuizApiModels.Day> reopenQuiz(
            String quizDate, QuizApiModels.DayMutation mutation);

    /** Loads the privacy-limited custom question queue. */
    CompletableFuture<QuizApiModels.CustomQueue> customQuizQueue();

    /** Queues one guided custom question. */
    CompletableFuture<QuizApiModels.CustomQuestion> createCustomQuiz(
            QuizApiModels.CustomMutation mutation);

    /** Hides and reports one RC5 question. */
    CompletableFuture<ApiModels.Message> reportQuizQuestion(
            String questionId, QuizApiModels.ReportMutation mutation);

    /** Loads countdowns. */
    CompletableFuture<List<CountdownApiModels.Countdown>> countdowns();

    /** Creates a countdown. */
    CompletableFuture<CountdownApiModels.Countdown> createCountdown(
            CountdownApiModels.Mutation mutation);

    /** Updates a countdown from its expected revision. */
    CompletableFuture<CountdownApiModels.Countdown> updateCountdown(
            String countdownId, CountdownApiModels.Mutation mutation);

    /** Replaces the caller's private reminder offsets for one shared event. */
    CompletableFuture<CountdownApiModels.Countdown> replaceCountdownReminders(
            String countdownId, List<Integer> offsetsMinutes);

    /** Deletes a countdown idempotently from its expected revision. */
    CompletableFuture<ApiModels.Message> deleteCountdown(
            String countdownId, CountdownApiModels.DeleteRequest request);

    /** Loads the latest content-free activity panel. */
    CompletableFuture<ActivityApiModels.Page> activity();

    /** Marks events through one visibly rendered sequence as seen. */
    CompletableFuture<Void> markActivitySeen(long throughSequence, String operationId);

    /** Loads the coordinate-free together-time estimate. */
    CompletableFuture<ApiModels.TogetherSummary> togetherSummary();

    /** Loads separate relationship-age and location-derived nearby values. */
    CompletableFuture<TogetherTimeModels.Summary> togetherSummaryV2();

    /** Loads pair age from the immutable pairing instant and the nearby estimate. */
    CompletableFuture<TogetherTimeModels.PairSummary> togetherSummaryV3();

    /** Sends one of the fixed Smooch choices. */
    CompletableFuture<SmoochApiModels.Sent> sendSmooch(SmoochApiModels.SendRequest request);

    /** Loads current Smooch capacity and the current non-competitive week recap. */
    CompletableFuture<SmoochApiModels.Status> smoochStatus();

    /** Loads pending partner Smooches for notification. */
    CompletableFuture<List<SmoochApiModels.Delivery>> pendingSmooches();

    /** Acknowledges notifications only after they were rendered. */
    CompletableFuture<Void> acknowledgeSmooches(List<String> ids);

    /** Loads account-wide notification choices. */
    CompletableFuture<NotificationApiModels.Preferences> notificationPreferences();

    /** Replaces all account-wide notification choices. */
    CompletableFuture<NotificationApiModels.Preferences> updateNotificationPreferences(
            NotificationApiModels.PreferencesUpdate request);

    /** Registers or heartbeats one random application-install identifier. */
    CompletableFuture<NotificationApiModels.Device> registerNotificationDevice(
            String deviceId, NotificationApiModels.DeviceUpsert request);

    /** Disables notification delivery for one application installation. */
    CompletableFuture<Void> disableNotificationDevice(String deviceId);

    /** Loads live notification events pending for one application installation. */
    CompletableFuture<List<NotificationApiModels.Event>> pendingNotifications(String deviceId);

    /** Acknowledges only events successfully posted by Android. */
    CompletableFuture<Void> acknowledgeNotifications(String deviceId, List<String> eventIds);

    /** Loads durable weekly Smooch totals. */
    CompletableFuture<List<SmoochApiModels.Week>> smoochWeeks(int weeks);

    /** Loads thirty coordinate-free UTC days of nearby estimates. */
    CompletableFuture<List<TogetherTimeModels.HistoryDay>> togetherHistory();

    /** Proposes a relationship start date for mutual approval. */
    CompletableFuture<TogetherTimeModels.StartDateProposal> proposeStartDate(
            TogetherTimeModels.ProposalRequest request);

    /** Accepts, declines, or cancels one current start-date proposal. */
    CompletableFuture<TogetherTimeModels.StartDateProposal> decideStartDate(
            String proposalId, TogetherTimeModels.DecisionRequest request);

    /** Lists recent correctable together-time minute buckets. */
    CompletableFuture<List<ApiModels.TogetherBucket>> togetherBuckets();

    /** Applies an audited correction and returns the updated estimate. */
    CompletableFuture<ApiModels.TogetherSummary> correctTogetherBucket(
            String bucketId, ApiModels.TogetherCorrectionRequest request);

    /** Loads note snapshots. */
    CompletableFuture<List<NoteApiModels.Note>> notes();

    /** Creates a note while its draft remains local. */
    CompletableFuture<NoteApiModels.Note> createNote(NoteApiModels.CreateRequest request);

    /** Loads archived notes still eligible for undo. */
    CompletableFuture<List<NoteApiModels.Note>> archivedNotes();

    /** Renames one note idempotently. */
    CompletableFuture<NoteApiModels.Note> renameNote(
            String noteId, NoteApiModels.TitleRequest request);

    /** Archives one note idempotently. */
    CompletableFuture<NoteApiModels.Note> archiveNote(
            String noteId, NoteApiModels.ArchiveRequest request);

    /** Restores one archived note idempotently. */
    CompletableFuture<NoteApiModels.Note> restoreNote(
            String noteId, NoteApiModels.ArchiveRequest request);

    /** Lists authorized attachments including upload and scan state. */
    CompletableFuture<List<NoteApiModels.Attachment>> noteAttachments(String noteId);

    /** Uploads one selected private file through bounded resumable chunks. */
    CompletableFuture<NoteApiModels.Attachment> uploadNoteAttachment(
            String noteId, String displayName, String mediaType, File file);

    /** Downloads verified sanitized bytes into the private preview cache. */
    CompletableFuture<File> downloadNoteAttachment(
            String noteId, NoteApiModels.Attachment attachment);

    /** Deletes private attachment bytes and metadata visibility for the current couple. */
    CompletableFuture<Void> deleteNoteAttachment(String noteId, String attachmentId);

    /** Loads revocable privacy settings. */
    CompletableFuture<ApiModels.Preferences> preferences();

    /** Applies a privacy-setting change. */
    CompletableFuture<ApiModels.Preferences> updatePreferences(
            ApiModels.PreferencesMutation mutation);

    /** Ends the active pairing. */
    CompletableFuture<ApiModels.UnpairResult> unpair();

    /** Lists the account's private former-pairing archives. */
    CompletableFuture<List<ApiModels.ArchiveSummary>> archives();

    /** Loads one private read-only former-pairing archive. */
    CompletableFuture<ApiModels.ArchiveDetail> archive(String archiveId);

    /** Loads a portable owner-visible export. */
    CompletableFuture<Map<String, Object>> exportAccount();

    /** Reauthenticates and schedules account erasure. */
    CompletableFuture<ApiModels.DeletionResult> deleteAccount(String password);
}
