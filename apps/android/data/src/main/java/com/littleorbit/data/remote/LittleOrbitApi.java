package com.littleorbit.data.remote;

import retrofit2.Call;
import retrofit2.http.Body;
import retrofit2.http.GET;
import retrofit2.http.HTTP;
import retrofit2.http.PATCH;
import retrofit2.http.POST;
import retrofit2.http.PUT;
import retrofit2.http.Path;
import retrofit2.http.Query;

/** Versioned Little Orbit HTTP contract used by repositories only. */
public interface LittleOrbitApi {
    /** Checks API liveness without sending credentials. */
    @GET("api/v1/health/live")
    Call<HealthDto> health();

    /** Loads public signed-APK update metadata without requiring an account session. */
    @GET("api/v1/releases/current")
    Call<ApiModels.ApkRelease> currentRelease();

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
    Call<java.util.List<ApiModels.Note>> notes();

    /** Creates a note while keeping the local draft until acknowledgement. */
    @POST("api/v1/notes")
    Call<ApiModels.Note> createNote(@Body ApiModels.NoteCreateRequest request);

    /** Loads the current estimate without coordinates. */
    @GET("api/v1/together-time")
    Call<ApiModels.TogetherSummary> togetherSummary();

    /** Lists coordinate-free correctable estimate minutes. */
    @GET("api/v1/together-time/buckets")
    Call<java.util.List<ApiModels.TogetherBucket>> togetherBuckets();

    /** Applies an audited correction to one estimate minute. */
    @PATCH("api/v1/together-time/buckets/{bucketId}")
    Call<ApiModels.TogetherSummary> correctTogetherBucket(
            @Path("bucketId") String bucketId,
            @Body ApiModels.TogetherCorrectionRequest request);

    /** Uploads a bounded encrypted-queue batch after consent checks. */
    @POST("api/v1/together-time/locations")
    Call<ApiModels.LocationBatchResult> uploadLocations(@Body ApiModels.LocationBatch request);

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
