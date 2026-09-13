package com.littleorbit.data.remote;

import retrofit2.Call;
import retrofit2.http.Body;
import retrofit2.http.DELETE;
import retrofit2.http.GET;
import retrofit2.http.Headers;
import retrofit2.http.HTTP;
import retrofit2.http.PATCH;
import retrofit2.http.POST;
import retrofit2.http.PUT;
import retrofit2.http.Path;
import retrofit2.http.Query;
import retrofit2.http.Streaming;

/** Versioned Little Orbit HTTP contract used by repositories only. */
public interface LittleOrbitApi {
    /** Checks API liveness without sending credentials. */
    @GET("api/v1/health/live")
    Call<HealthDto> health();

    /** Loads public signed-APK update metadata without requiring an account session. */
    @GET("api/v1/releases/current")
    Call<ApiModels.ApkRelease> currentRelease();

    /** Loads the caller and currently authorized partner display identities. */
    @GET("api/v1/account/orbit-profile")
    Call<ProfileApiModels.OrbitProfile> orbitProfile();

    /** Loads the caller's normalized private profile image. */
    @Streaming
    @GET("api/v1/account/profile-photo")
    Call<okhttp3.ResponseBody> profilePhoto(@Query("thumbnail") boolean thumbnail);

    /** Loads the active partner image only after couple authorization. */
    @Streaming
    @GET("api/v1/couple/current/partner-profile-photo")
    Call<okhttp3.ResponseBody> partnerProfilePhoto(@Query("thumbnail") boolean thumbnail);

    /** Replaces the caller's profile image with normalized WebP bytes. */
    @Headers("Content-Type: image/webp")
    @PUT("api/v1/account/profile-photo")
    Call<ProfileApiModels.PhotoMetadata> putProfilePhoto(@Body okhttp3.RequestBody image);

    /** Idempotently removes the caller's profile image. */
    @DELETE("api/v1/account/profile-photo")
    Call<Void> deleteProfilePhoto();

    /** Authenticates a verified account. */
    @POST("api/v1/auth/login")
    Call<ApiModels.SessionResponse> login(@Body ApiModels.LoginRequest request);

    /** Rotates the current opaque session. */
    @POST("api/v1/auth/session/rotate")
    Call<ApiModels.SessionResponse> rotateSession();

    /** Revokes the current opaque session. */
    @POST("api/v1/auth/logout")
    Call<ApiModels.Message> logout();

    /** Creates a ten-minute pair code. */
    @POST("api/v1/pairing/codes")
    Call<ApiModels.PairCodeResponse> createPairCode();

    /** Reserves a pair code pending creator confirmation. */
    @POST("api/v1/pairing/redeem")
    Call<ApiModels.PairingState> redeemPairCode(@Body ApiModels.PairRedeemRequest request);

    /** Loads the reserved partner for creator confirmation. */
    @GET("api/v1/pairing/pending")
    Call<ApiModels.PendingPairing> pendingPairing();

    /** Confirms a reserved pairing request. */
    @POST("api/v1/pairing/confirm")
    Call<ApiModels.PairingState> confirmPairing(@Body ApiModels.PairConfirmRequest request);

    /** Loads exactly five questions for a local calendar date. */
    @GET("api/v1/quizzes/daily")
    Call<java.util.List<ApiModels.Question>> dailyQuestions(@Query("local_date") String localDate);

    /** Submits an answer without revealing either answer early. */
    @PUT("api/v1/quizzes/daily/{questionId}/answer")
    Call<java.util.List<ApiModels.Question>> submitAnswer(
            @Path("questionId") String questionId, @Body ApiModels.AnswerRequest request);

    /** Creates a couple-scoped custom question. */
    @POST("api/v1/quizzes/custom")
    Call<ApiModels.Question> createCustomQuestion(@Body ApiModels.CustomQuestionRequest request);

    /** Hides a question for this couple and queues owner review. */
    @POST("api/v1/quizzes/{questionId}/report")
    Call<ApiModels.Message> reportQuestion(
            @Path("questionId") String questionId,
            @Body ApiModels.QuestionReportRequest request);

    /** Loads the server-authoritative UTC quiz day for RC5. */
    @GET("api/v2/quizzes/today")
    Call<QuizApiModels.Day> quizToday();

    /** Loads one current or historical UTC quiz day. */
    @GET("api/v2/quizzes/days/{quizDate}")
    Call<QuizApiModels.Day> quizDay(@Path("quizDate") String quizDate);

    /** Loads the fixed thirty-day content-free history. */
    @GET("api/v2/quizzes/history")
    Call<java.util.List<QuizApiModels.HistoryItem>> quizHistory(@Query("days") int days);

    /** Loads content-free quiz completion state for delayed polling. */
    @GET("api/v2/quizzes/status")
    Call<QuizApiModels.Status> quizStatus();

    /** Saves one revisioned private answer draft. */
    @PUT("api/v2/quizzes/days/{quizDate}/questions/{questionId}/draft")
    Call<QuizApiModels.Day> saveQuizDraft(
            @Path("quizDate") String quizDate,
            @Path("questionId") String questionId,
            @Body QuizApiModels.DraftMutation request);

    /** Finishes the caller's reviewed daily quiz. */
    @POST("api/v2/quizzes/days/{quizDate}/finish")
    Call<QuizApiModels.Day> finishQuiz(
            @Path("quizDate") String quizDate, @Body QuizApiModels.DayMutation request);

    /** Reopens the caller's daily quiz while shared reveal is pending. */
    @POST("api/v2/quizzes/days/{quizDate}/reopen")
    Call<QuizApiModels.Day> reopenQuiz(
            @Path("quizDate") String quizDate, @Body QuizApiModels.DayMutation request);

    /** Loads creator-visible custom prompts and a partner surprise count. */
    @GET("api/v2/quizzes/custom")
    Call<QuizApiModels.CustomQueue> customQuizQueue();

    /** Queues a guided custom question. */
    @POST("api/v2/quizzes/custom")
    Call<QuizApiModels.CustomQuestion> createCustomQuiz(
            @Body QuizApiModels.CustomMutation request);

    /** Hides one question and requests a safe replacement. */
    @POST("api/v2/quizzes/questions/{questionId}/report")
    Call<ApiModels.Message> reportQuizQuestion(
            @Path("questionId") String questionId,
            @Body QuizApiModels.ReportMutation request);

    /** Loads active shared countdowns. */
    @GET("api/v1/countdowns")
    Call<java.util.List<ApiModels.Countdown>> countdowns();

    /** Creates a shared countdown idempotently. */
    @POST("api/v1/countdowns")
    Call<ApiModels.Countdown> createCountdown(@Body ApiModels.CountdownMutation request);

    /** Updates a shared countdown from an expected revision. */
    @PUT("api/v1/countdowns/{countdownId}")
    Call<ApiModels.Countdown> updateCountdown(
            @Path("countdownId") String countdownId, @Body ApiModels.CountdownMutation request);

    /** Deletes a shared countdown from an expected revision. */
    @HTTP(method = "DELETE", path = "api/v1/countdowns/{countdownId}", hasBody = true)
    Call<ApiModels.Message> deleteCountdown(
            @Path("countdownId") String countdownId,
            @Body ApiModels.CountdownDeleteRequest request);

    /** Loads note snapshots for offline caching. */
    @GET("api/v1/notes")
    Call<java.util.List<NoteApiModels.Note>> notes();

    /** Creates a note while keeping the local draft until acknowledgement. */
    @POST("api/v1/notes")
    Call<NoteApiModels.Note> createNote(@Body NoteApiModels.CreateRequest request);

    /** Loads notes still inside their seven-day undo window. */
    @GET("api/v1/notes/archived")
    Call<java.util.List<NoteApiModels.Note>> archivedNotes();

    /** Renames a note without advancing body OT revisions. */
    @PATCH("api/v1/notes/{noteId}")
    Call<NoteApiModels.Note> renameNote(
            @Path("noteId") String noteId, @Body NoteApiModels.TitleRequest request);

    /** Archives a note for seven-day undo. */
    @POST("api/v1/notes/{noteId}/archive")
    Call<NoteApiModels.Note> archiveNote(
            @Path("noteId") String noteId, @Body NoteApiModels.ArchiveRequest request);

    /** Restores a note during its undo window. */
    @POST("api/v1/notes/{noteId}/restore")
    Call<NoteApiModels.Note> restoreNote(
            @Path("noteId") String noteId, @Body NoteApiModels.ArchiveRequest request);

    /** Sends one fixed-emoji Smooch idempotently. */
    @POST("api/v1/smooches")
    Call<SmoochApiModels.Sent> sendSmooch(@Body SmoochApiModels.SendRequest request);

    /** Loads pending Smooch notifications for this recipient. */
    @GET("api/v1/smooches/pending")
    Call<java.util.List<SmoochApiModels.Delivery>> pendingSmooches();

    /** Marks rendered Smooch notifications as delivered. */
    @POST("api/v1/smooches/deliveries/ack")
    Call<Void> acknowledgeSmooches(@Body SmoochApiModels.DeliveryAck request);

    /** Loads calendar-week Smooch history. */
    @GET("api/v1/smooches/weeks")
    Call<java.util.List<SmoochApiModels.Week>> smoochWeeks(@Query("weeks") int weeks);

    /** Loads the current estimate without coordinates. */
    @GET("api/v1/together-time")
    Call<ApiModels.TogetherSummary> togetherSummary();

    /** Loads separate relationship-age and nearby-time values. */
    @GET("api/v2/together-time")
    Call<TogetherTimeModels.Summary> togetherSummaryV2();

    /** Loads immutable pair age and the separate location-derived estimate. */
    @GET("api/v3/together-time")
    Call<TogetherTimeModels.PairSummary> togetherSummaryV3();

    /** Loads thirty coordinate-free UTC days of nearby estimates. */
    @GET("api/v2/together-time/history")
    Call<java.util.List<TogetherTimeModels.HistoryDay>> togetherHistory(@Query("days") int days);

    /** Proposes a shared start date for partner approval. */
    @POST("api/v2/together-time/start-date-proposals")
    Call<TogetherTimeModels.StartDateProposal> proposeStartDate(
            @Body TogetherTimeModels.ProposalRequest request);

    /** Decides a current shared start-date proposal. */
    @POST("api/v2/together-time/start-date-proposals/{proposalId}/decision")
    Call<TogetherTimeModels.StartDateProposal> decideStartDate(
            @Path("proposalId") String proposalId,
            @Body TogetherTimeModels.DecisionRequest request);

    /** Lists coordinate-free correctable estimate minutes. */
    @GET("api/v1/together-time/buckets")
    Call<java.util.List<ApiModels.TogetherBucket>> togetherBuckets();

    /** Applies an audited correction to one estimate minute. */
    @PATCH("api/v1/together-time/buckets/{bucketId}")
    Call<ApiModels.TogetherSummary> correctTogetherBucket(
            @Path("bucketId") String bucketId,
            @Body ApiModels.TogetherCorrectionRequest request);

    /** Uploads a bounded encrypted-queue batch after consent checks. */
    @POST("api/v2/together-time/locations")
    Call<TogetherTimeModels.LocationBatchResult> uploadLocations(
            @Body ApiModels.LocationBatch request);

    /** Loads member and mutual privacy settings. */
    @GET("api/v1/couple/preferences")
    Call<ApiModels.Preferences> preferences();

    /** Applies an explicit privacy setting. */
    @PATCH("api/v1/couple/preferences")
    Call<ApiModels.Preferences> updatePreferences(@Body ApiModels.PreferencesMutation request);

    /** Ends sharing and creates private read-only archives. */
    @POST("api/v1/couple/unpair")
    Call<ApiModels.UnpairResult> unpair();

    /** Lists private read-only former-pairing summaries. */
    @GET("api/v1/couple/archives")
    Call<java.util.List<ApiModels.ArchiveSummary>> archives();

    /** Loads one private former-pairing archive. */
    @GET("api/v1/couple/archives/{archiveId}")
    Call<ApiModels.ArchiveDetail> archive(@Path("archiveId") String archiveId);

    /** Exports owner-visible account data. */
    @GET("api/v1/account/export")
    Call<java.util.Map<String, Object>> exportAccount();

    /** Stops access and schedules full account erasure. */
    @POST("api/v1/account/deletion")
    Call<ApiModels.DeletionResult> deleteAccount(@Body ApiModels.DeletionRequest request);
}
