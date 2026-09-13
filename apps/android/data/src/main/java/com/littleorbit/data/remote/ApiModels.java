package com.littleorbit.data.remote;

import com.squareup.moshi.Json;
import java.util.List;
import java.util.Map;

/** Versioned HTTP DTOs kept separate from domain and screen state. */
public final class ApiModels {
    private ApiModels() {}

    /** Public metadata for one immutable signed phone APK. */
    public static final class ApkRelease {
        public final String version;
        @Json(name = "version_code") public final int versionCode;
        @Json(name = "apk_url") public final String apkUrl;
        @Json(name = "github_release_url") public final String githubReleaseUrl;
        public final String sha256;
        @Json(name = "size_bytes") public final long sizeBytes;
        @Json(name = "package_name") public final String packageName;
        @Json(name = "signer_sha256") public final String signerSha256;
        @Json(name = "wear_apk_url") public final String wearApkUrl;
        @Json(name = "wear_sha256") public final String wearSha256;
        @Json(name = "wear_size_bytes") public final Long wearSizeBytes;
        @Json(name = "wear_package_name") public final String wearPackageName;
        @Json(name = "wear_version_code") public final Integer wearVersionCode;
        @Json(name = "wear_minimum_android") public final Integer wearMinimumAndroid;
        @Json(name = "minimum_android") public final int minimumAndroid;
        @Json(name = "minimum_supported_version_code")
        public final int minimumSupportedVersionCode;
        @Json(name = "required_after") public final String requiredAfter;
        @Json(name = "release_notes") public final String releaseNotes;
        @Json(name = "published_at") public final String publishedAt;

        /** Creates a decoded release response. */
        public ApkRelease(
                String version,
                int versionCode,
                String apkUrl,
                String githubReleaseUrl,
                String sha256,
                long sizeBytes,
                String packageName,
                String signerSha256,
                int minimumAndroid,
                int minimumSupportedVersionCode,
                String requiredAfter,
                String releaseNotes,
                String publishedAt) {
            this.version = version; this.versionCode = versionCode;
            this.apkUrl = apkUrl; this.githubReleaseUrl = githubReleaseUrl;
            this.sha256 = sha256; this.sizeBytes = sizeBytes;
            this.packageName = packageName; this.signerSha256 = signerSha256;
            this.wearApkUrl = null; this.wearSha256 = null;
            this.wearSizeBytes = null; this.wearPackageName = null;
            this.wearVersionCode = null; this.wearMinimumAndroid = null;
            this.minimumAndroid = minimumAndroid;
            this.minimumSupportedVersionCode = minimumSupportedVersionCode;
            this.requiredAfter = requiredAfter; this.releaseNotes = releaseNotes;
            this.publishedAt = publishedAt;
        }
    }

    /** Email/password sign-in request. */
    public static final class LoginRequest {
        public final String email;
        public final String password;

        /** Creates a bounded credential request. */
        public LoginRequest(String email, String password) {
            this.email = email;
            this.password = password;
        }
    }

    /** Opaque authenticated session response. */
    public static final class SessionResponse {
        @Json(name = "access_token") public final String accessToken;
        @Json(name = "expires_at") public final String expiresAt;
        @Json(name = "account_id") public final String accountId;

        /** Creates a decoded server session. */
        public SessionResponse(String accessToken, String expiresAt, String accountId) {
            this.accessToken = accessToken;
            this.expiresAt = expiresAt;
            this.accountId = accountId;
        }
    }

    /** Pair-code response shown to its creator. */
    public static final class PairCodeResponse {
        public final String code;
        @Json(name = "expires_at") public final String expiresAt;

        /** Creates pair-code display data. */
        public PairCodeResponse(String code, String expiresAt) {
            this.code = code;
            this.expiresAt = expiresAt;
        }
    }

    /** Pair-code redemption request. */
    public static final class PairRedeemRequest {
        public final String code;

        /** Creates a redemption request. */
        public PairRedeemRequest(String code) { this.code = code; }
    }

    /** Creator confirmation request. */
    public static final class PairConfirmRequest {
        @Json(name = "request_id") public final String requestId;

        /** Creates a confirmation request. */
        public PairConfirmRequest(String requestId) { this.requestId = requestId; }
    }

    /** Pairing transition result. */
    public static final class PairingState {
        public final String state;
        @Json(name = "request_id") public final String requestId;
        @Json(name = "couple_id") public final String coupleId;

        /** Creates pairing state. */
        public PairingState(String state, String requestId, String coupleId) {
            this.state = state;
            this.requestId = requestId;
            this.coupleId = coupleId;
        }
    }

    /** Pending partner metadata shown only to the code creator. */
    public static final class PendingPairing {
        @Json(name = "request_id") public final String requestId;
        @Json(name = "partner_display_name") public final String partnerDisplayName;
        @Json(name = "expires_at") public final String expiresAt;

        /** Creates decoded confirmation metadata. */
        public PendingPairing(String requestId, String partnerDisplayName, String expiresAt) {
            this.requestId = requestId;
            this.partnerDisplayName = partnerDisplayName;
            this.expiresAt = expiresAt;
        }
    }

    /** Daily question and reveal state. */
    public static final class Question {
        public final String id;
        @Json(name = "publish_date") public final String publishDate;
        public final String kind;
        public final String prompt;
        public final String category;
        public final List<String> options;
        @Json(name = "submitted_by_me") public final boolean submittedByMe;
        @Json(name = "both_submitted") public final boolean bothSubmitted;
        @Json(name = "my_answer") public final Map<String, Object> myAnswer;
        @Json(name = "partner_answer") public final Map<String, Object> partnerAnswer;

        /** Creates a decoded daily question. */
        public Question(
                String id,
                String publishDate,
                String kind,
                String prompt,
                String category,
                List<String> options,
                boolean submittedByMe,
                boolean bothSubmitted,
                Map<String, Object> myAnswer,
                Map<String, Object> partnerAnswer) {
            this.id = id;
            this.publishDate = publishDate;
            this.kind = kind;
            this.prompt = prompt;
            this.category = category;
            this.options = List.copyOf(options);
            this.submittedByMe = submittedByMe;
            this.bothSubmitted = bothSubmitted;
            this.myAnswer = myAnswer;
            this.partnerAnswer = partnerAnswer;
        }
    }

    /** Type-specific answer envelope. */
    public static final class AnswerRequest {
        public final Map<String, Object> answer;

        /** Creates an answer request. */
        public AnswerRequest(Map<String, Object> answer) { this.answer = Map.copyOf(answer); }
    }

    /** Couple-authored question input under the shared consent rules. */
    public static final class CustomQuestionRequest {
        @Json(name = "publish_date") public final String publishDate;
        public final String kind;
        public final String prompt;
        public final String category;
        public final boolean intimacy;
        public final List<String> options;

        /** Creates a validated custom-question payload. */
        public CustomQuestionRequest(
                String publishDate,
                String kind,
                String prompt,
                String category,
                boolean intimacy,
                List<String> options) {
            this.publishDate = publishDate;
            this.kind = kind;
            this.prompt = prompt;
            this.category = category;
            this.intimacy = intimacy;
            this.options = List.copyOf(options);
        }
    }

    /** Privacy-safe reason for hiding a question from the current couple. */
    public static final class QuestionReportRequest {
        public final String reason;

        /** Creates a report payload. */
        public QuestionReportRequest(String reason) {
            this.reason = reason;
        }
    }

    /** Shared countdown response. */
    public static final class Countdown {
        public final String id;
        public final String title;
        @Json(name = "occurs_at") public final String occursAt;
        public final String timezone;
        public final String notes;
        public final int revision;
        @Json(name = "updated_at") public final String updatedAt;
        @Json(ignore = true) public final boolean pendingSync;
        @Json(ignore = true) public final boolean syncConflict;

        /** Creates decoded countdown state. */
        public Countdown(
                String id,
                String title,
                String occursAt,
                String timezone,
                String notes,
                int revision,
                String updatedAt) {
            this(id, title, occursAt, timezone, notes, revision, updatedAt, false, false);
        }

        /** Creates decoded or optimistic countdown state. */
        public Countdown(
                String id,
                String title,
                String occursAt,
                String timezone,
                String notes,
                int revision,
                String updatedAt,
                boolean pendingSync,
                boolean syncConflict) {
            this.id = id;
            this.title = title;
            this.occursAt = occursAt;
            this.timezone = timezone;
            this.notes = notes;
            this.revision = revision;
            this.updatedAt = updatedAt;
            this.pendingSync = pendingSync;
            this.syncConflict = syncConflict;
        }
    }

    /** Retry-safe countdown mutation. */
    public static final class CountdownMutation {
        @Json(name = "operation_id") public final String operationId;
        public final String title;
        @Json(name = "occurs_at") public final String occursAt;
        public final String timezone;
        public final String notes;
        @Json(name = "expected_revision") public final Integer expectedRevision;

        /** Creates a countdown mutation. */
        public CountdownMutation(
                String operationId,
                String title,
                String occursAt,
                String timezone,
                String notes,
                Integer expectedRevision) {
            this.operationId = operationId;
            this.title = title;
            this.occursAt = occursAt;
            this.timezone = timezone;
            this.notes = notes;
            this.expectedRevision = expectedRevision;
        }
    }

    /** Retry-safe optimistic countdown deletion. */
    public static final class CountdownDeleteRequest {
        @Json(name = "operation_id") public final String operationId;
        @Json(name = "expected_revision") public final int expectedRevision;

        /** Creates a countdown deletion request. */
        public CountdownDeleteRequest(String operationId, int expectedRevision) {
            this.operationId = operationId;
            this.expectedRevision = expectedRevision;
        }
    }

    /** Together-time aggregate without coordinates. */
    public static final class TogetherSummary {
        @Json(name = "estimated_seconds") public final long estimatedSeconds;
        @Json(name = "last_updated_at") public final String lastUpdatedAt;
        @Json(name = "proximity_threshold_m") public final double proximityThresholdM;
        public final String label;

        /** Creates a decoded estimate. */
        public TogetherSummary(
                long estimatedSeconds,
                String lastUpdatedAt,
                double proximityThresholdM,
                String label) {
            this.estimatedSeconds = estimatedSeconds;
            this.lastUpdatedAt = lastUpdatedAt;
            this.proximityThresholdM = proximityThresholdM;
            this.label = label;
        }
    }

    /** Correctable together-time minute with no coordinate data. */
    public static final class TogetherBucket {
        public final String id;
        @Json(name = "bucket_start") public final String bucketStart;
        @Json(name = "duration_seconds") public final int durationSeconds;
        @Json(name = "corrected_at") public final String correctedAt;

        /** Creates a coordinate-free estimate bucket. */
        public TogetherBucket(
                String id, String bucketStart, int durationSeconds, String correctedAt) {
            this.id = id;
            this.bucketStart = bucketStart;
            this.durationSeconds = durationSeconds;
            this.correctedAt = correctedAt;
        }
    }

    /** Audited user correction to one estimate minute. */
    public static final class TogetherCorrectionRequest {
        @Json(name = "duration_seconds") public final int durationSeconds;
        public final String reason;

        /** Creates a bounded correction. */
        public TogetherCorrectionRequest(int durationSeconds, String reason) {
            this.durationSeconds = durationSeconds;
            this.reason = reason;
        }
    }

    /** One coordinate sample carried only between encrypted queue and API. */
    public static final class LocationSample {
        @Json(name = "sample_id") public final String sampleId;
        @Json(name = "recorded_at") public final String recordedAt;
        public final double latitude;
        public final double longitude;
        @Json(name = "accuracy_m") public final double accuracyM;

        /** Creates a consented upload sample. */
        public LocationSample(
                String sampleId,
                String recordedAt,
                double latitude,
                double longitude,
                double accuracyM) {
            this.sampleId = sampleId;
            this.recordedAt = recordedAt;
            this.latitude = latitude;
            this.longitude = longitude;
            this.accuracyM = accuracyM;
        }
    }

    /** Bounded retry-safe location upload. */
    public static final class LocationBatch {
        public final List<LocationSample> samples;

        /** Creates an immutable upload batch. */
        public LocationBatch(List<LocationSample> samples) {
            this.samples = List.copyOf(samples);
        }
    }

    /** Coordinate-free ingestion acknowledgement. */
    public static final class LocationBatchResult {
        public final int accepted;
        public final int duplicates;
        @Json(name = "together_minutes_added") public final int togetherMinutesAdded;

        /** Creates a decoded ingestion result. */
        public LocationBatchResult(int accepted, int duplicates, int togetherMinutesAdded) {
            this.accepted = accepted;
            this.duplicates = duplicates;
            this.togetherMinutesAdded = togetherMinutesAdded;
        }
    }

    /** Member and mutual consent response. */
    public static final class Preferences {
        @Json(name = "couple_id") public final String coupleId;
        @Json(name = "anniversary_date") public final String anniversaryDate;
        @Json(name = "proximity_threshold_m") public final double thresholdM;
        @Json(name = "intimacy_enabled_by_me") public final boolean intimacyByMe;
        @Json(name = "intimacy_enabled_by_both") public final boolean intimacyByBoth;
        @Json(name = "location_enabled_by_me") public final boolean locationByMe;
        @Json(name = "location_enabled_by_both") public final boolean locationByBoth;
        @Json(name = "home_timezone") public final String homeTimezone;

        /** Creates decoded privacy settings. */
        public Preferences(
                String coupleId,
                String anniversaryDate,
                double thresholdM,
                boolean intimacyByMe,
                boolean intimacyByBoth,
                boolean locationByMe,
                boolean locationByBoth) {
            this(coupleId, anniversaryDate, thresholdM, intimacyByMe, intimacyByBoth,
                    locationByMe, locationByBoth, "America/Los_Angeles");
        }

        /** Creates decoded consent and couple calendar settings. */
        public Preferences(
                String coupleId,
                String anniversaryDate,
                double thresholdM,
                boolean intimacyByMe,
                boolean intimacyByBoth,
                boolean locationByMe,
                boolean locationByBoth,
                String homeTimezone) {
            this.coupleId = coupleId;
            this.anniversaryDate = anniversaryDate;
            this.thresholdM = thresholdM;
            this.intimacyByMe = intimacyByMe;
            this.intimacyByBoth = intimacyByBoth;
            this.locationByMe = locationByMe;
            this.locationByBoth = locationByBoth;
            this.homeTimezone = homeTimezone;
        }
    }

    /** Partial privacy-setting mutation. */
    public static final class PreferencesMutation {
        @Json(name = "intimacy_enabled") public final Boolean intimacyEnabled;
        @Json(name = "location_enabled") public final Boolean locationEnabled;
        @Json(name = "proximity_threshold_m") public final Double thresholdM;
        @Json(name = "home_timezone") public final String homeTimezone;

        /** Creates an explicit consent mutation. */
        public PreferencesMutation(
                Boolean intimacyEnabled,
                Boolean locationEnabled,
                Double thresholdM) {
            this(intimacyEnabled, locationEnabled, thresholdM, null);
        }

        /** Creates an explicit consent or home-calendar mutation. */
        public PreferencesMutation(
                Boolean intimacyEnabled,
                Boolean locationEnabled,
                Double thresholdM,
                String homeTimezone) {
            this.intimacyEnabled = intimacyEnabled;
            this.locationEnabled = locationEnabled;
            this.thresholdM = thresholdM;
            this.homeTimezone = homeTimezone;
        }
    }

    /** Neutral server message. */
    public static final class Message {
        public final String message;

        /** Creates a decoded message. */
        public Message(String message) { this.message = message; }
    }

    /** Unpair result that identifies the caller's private archive. */
    public static final class UnpairResult {
        @Json(name = "archive_id") public final String archiveId;
        @Json(name = "ended_at") public final String endedAt;

        /** Creates a decoded unpair result. */
        public UnpairResult(String archiveId, String endedAt) {
            this.archiveId = archiveId;
            this.endedAt = endedAt;
        }
    }

    /** Private read-only former-pairing metadata. */
    public static class ArchiveSummary {
        @Json(name = "archive_id") public final String archiveId;
        @Json(name = "partner_display_name") public final String partnerDisplayName;
        @Json(name = "joined_at") public final String joinedAt;
        @Json(name = "ended_at") public final String endedAt;

        /** Creates former-pairing metadata. */
        public ArchiveSummary(
                String archiveId, String partnerDisplayName, String joinedAt, String endedAt) {
            this.archiveId = archiveId;
            this.partnerDisplayName = partnerDisplayName;
            this.joinedAt = joinedAt;
            this.endedAt = endedAt;
        }
    }

    /** Private former-pairing content that can never enter a new couple. */
    public static final class ArchiveDetail extends ArchiveSummary {
        public final List<Map<String, Object>> notes;
        public final List<Map<String, Object>> countdowns;
        @Json(name = "quiz_answers") public final List<Map<String, Object>> quizAnswers;
        public final List<Map<String, Object>> smooches;

        /** Creates an immutable archive response. */
        public ArchiveDetail(
                String archiveId,
                String partnerDisplayName,
                String joinedAt,
                String endedAt,
                List<Map<String, Object>> notes,
                List<Map<String, Object>> countdowns,
                List<Map<String, Object>> quizAnswers,
                List<Map<String, Object>> smooches) {
            super(archiveId, partnerDisplayName, joinedAt, endedAt);
            this.notes = List.copyOf(notes);
            this.countdowns = List.copyOf(countdowns);
            this.quizAnswers = List.copyOf(quizAnswers);
            this.smooches = smooches == null ? List.of() : List.copyOf(smooches);
        }
    }

    /** Recent-password account deletion request. */
    public static final class DeletionRequest {
        public final String password;

        /** Creates deletion proof. */
        public DeletionRequest(String password) { this.password = password; }
    }

    /** Scheduled erasure response. */
    public static final class DeletionResult {
        @Json(name = "job_id") public final String jobId;
        @Json(name = "execute_after") public final String executeAfter;

        /** Creates decoded deletion schedule. */
        public DeletionResult(String jobId, String executeAfter) {
            this.jobId = jobId;
            this.executeAfter = executeAfter;
        }
    }
}
