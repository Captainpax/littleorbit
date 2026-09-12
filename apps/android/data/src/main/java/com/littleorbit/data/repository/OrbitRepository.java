package com.littleorbit.data.repository;

import com.littleorbit.data.remote.ApiModels;
import com.littleorbit.data.remote.QuizApiModels;
import java.util.List;
import java.util.Map;
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
    CompletableFuture<List<ApiModels.Countdown>> countdowns();

    /** Creates a countdown. */
    CompletableFuture<ApiModels.Countdown> createCountdown(ApiModels.CountdownMutation mutation);

    /** Updates a countdown from its expected revision. */
    CompletableFuture<ApiModels.Countdown> updateCountdown(
            String countdownId, ApiModels.CountdownMutation mutation);

    /** Deletes a countdown idempotently from its expected revision. */
    CompletableFuture<ApiModels.Message> deleteCountdown(
            String countdownId, ApiModels.CountdownDeleteRequest request);

    /** Loads the coordinate-free together-time estimate. */
    CompletableFuture<ApiModels.TogetherSummary> togetherSummary();

    /** Lists recent correctable together-time minute buckets. */
    CompletableFuture<List<ApiModels.TogetherBucket>> togetherBuckets();

    /** Applies an audited correction and returns the updated estimate. */
    CompletableFuture<ApiModels.TogetherSummary> correctTogetherBucket(
            String bucketId, ApiModels.TogetherCorrectionRequest request);

    /** Loads note snapshots. */
    CompletableFuture<List<ApiModels.Note>> notes();

    /** Creates a note while its draft remains local. */
    CompletableFuture<ApiModels.Note> createNote(ApiModels.NoteCreateRequest request);

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
