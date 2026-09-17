package com.littleorbit.data.remote;

import com.squareup.moshi.Json;
import java.util.List;

/** RC6 relationship-age and coordinate-free nearby-time HTTP DTOs. */
public final class TogetherTimeModels {
    private TogetherTimeModels() {}

    /** Bounded retry-safe location upload scoped to one exact relationship. */
    public static final class LocationBatch {
        @Json(name = "relationship_id") public final String relationshipId;
        public final List<ApiModels.LocationSample> samples;

        /** Creates an immutable upload batch. */
        public LocationBatch(String relationshipId, List<ApiModels.LocationSample> samples) {
            this.relationshipId = relationshipId;
            this.samples = List.copyOf(samples);
        }
    }

    /** RC10 pair-age state derived from the immutable server pairing instant. */
    public static final class PairSummary {
        @Json(name = "relationship_id") public final String relationshipId;
        @Json(name = "paired_at") public final String pairedAt;
        @Json(name = "paired_days") public final long pairedDays;
        @Json(name = "nearby_observed_seconds") public final long nearbyObservedSeconds;
        @Json(name = "nearby_estimated_seconds") public final long nearbyEstimatedSeconds;
        @Json(name = "nearby_provisional_seconds") public final long nearbyProvisionalSeconds;
        @Json(name = "server_now") public final String serverNow;
        @Json(name = "counting_state") public final String countingState;
        @Json(name = "counting_anchor_at") public final String countingAnchorAt;
        @Json(name = "counting_live_until") public final String countingLiveUntil;
        @Json(name = "nearby_last_processed_at") public final String nearbyLastProcessedAt;
        @Json(name = "nearby_confidence") public final String nearbyConfidence;
        @Json(name = "algorithm_version") public final int algorithmVersion;
        @Json(name = "includes_legacy_estimates") public final boolean includesLegacyEstimates;
        @Json(name = "proximity_threshold_m") public final double proximityThresholdM;
        @Json(name = "location_enabled_by_me") public final boolean locationByMe;
        @Json(name = "location_enabled_by_both") public final boolean locationByBoth;
        public final String label;

        /** Creates one decoded privacy-limited pair and estimate summary. */
        public PairSummary(String relationshipId, String pairedAt, long pairedDays,
                long nearbyObservedSeconds, long nearbyEstimatedSeconds,
                long nearbyProvisionalSeconds, String serverNow, String countingState,
                String countingAnchorAt, String countingLiveUntil, String nearbyLastProcessedAt,
                String nearbyConfidence, int algorithmVersion, boolean includesLegacyEstimates,
                double proximityThresholdM, boolean locationByMe, boolean locationByBoth,
                String label) {
            this.relationshipId = relationshipId;
            this.pairedAt = pairedAt;
            this.pairedDays = pairedDays;
            this.nearbyObservedSeconds = nearbyObservedSeconds;
            this.nearbyEstimatedSeconds = nearbyEstimatedSeconds;
            this.nearbyProvisionalSeconds = nearbyProvisionalSeconds;
            this.serverNow = serverNow;
            this.countingState = countingState;
            this.countingAnchorAt = countingAnchorAt;
            this.countingLiveUntil = countingLiveUntil;
            this.nearbyLastProcessedAt = nearbyLastProcessedAt;
            this.nearbyConfidence = nearbyConfidence;
            this.algorithmVersion = algorithmVersion;
            this.includesLegacyEstimates = includesLegacyEstimates;
            this.proximityThresholdM = proximityThresholdM;
            this.locationByMe = locationByMe;
            this.locationByBoth = locationByBoth;
            this.label = label;
        }
    }

    /** Separate relationship-age and nearby-time state. */
    public static final class Summary {
        @Json(name = "relationship_start_date") public final String relationshipStartDate;
        @Json(name = "relationship_days") public final Long relationshipDays;
        @Json(name = "nearby_estimated_seconds") public final long nearbyEstimatedSeconds;
        @Json(name = "nearby_last_processed_at") public final String nearbyLastProcessedAt;
        @Json(name = "proximity_threshold_m") public final double proximityThresholdM;
        @Json(name = "location_enabled_by_me") public final boolean locationByMe;
        @Json(name = "location_enabled_by_both") public final boolean locationByBoth;
        public final String label;
        @Json(name = "pending_start_date") public final StartDateProposal pendingStartDate;

        /** Creates one decoded privacy-limited summary. */
        public Summary(
                String relationshipStartDate,
                Long relationshipDays,
                long nearbyEstimatedSeconds,
                String nearbyLastProcessedAt,
                double proximityThresholdM,
                boolean locationByMe,
                boolean locationByBoth,
                String label,
                StartDateProposal pendingStartDate) {
            this.relationshipStartDate = relationshipStartDate;
            this.relationshipDays = relationshipDays;
            this.nearbyEstimatedSeconds = nearbyEstimatedSeconds;
            this.nearbyLastProcessedAt = nearbyLastProcessedAt;
            this.proximityThresholdM = proximityThresholdM;
            this.locationByMe = locationByMe;
            this.locationByBoth = locationByBoth;
            this.label = label;
            this.pendingStartDate = pendingStartDate;
        }
    }

    /** One current relationship start-date proposal. */
    public static final class StartDateProposal {
        public final String id;
        @Json(name = "proposed_date") public final String proposedDate;
        @Json(name = "proposed_by_me") public final boolean proposedByMe;
        public final String status;
        @Json(name = "expires_at") public final String expiresAt;

        /** Creates a decoded proposal. */
        public StartDateProposal(
                String id,
                String proposedDate,
                boolean proposedByMe,
                String status,
                String expiresAt) {
            this.id = id;
            this.proposedDate = proposedDate;
            this.proposedByMe = proposedByMe;
            this.status = status;
            this.expiresAt = expiresAt;
        }
    }

    /** Retry-safe relationship start-date proposal mutation. */
    public static final class ProposalRequest {
        @Json(name = "operation_id") public final String operationId;
        @Json(name = "proposed_date") public final String proposedDate;

        /** Creates proposal input. */
        public ProposalRequest(String operationId, String proposedDate) {
            this.operationId = operationId;
            this.proposedDate = proposedDate;
        }
    }

    /** Retry-safe accept, decline, or cancel mutation. */
    public static final class DecisionRequest {
        @Json(name = "operation_id") public final String operationId;
        public final String decision;

        /** Creates decision input. */
        public DecisionRequest(String operationId, String decision) {
            this.operationId = operationId;
            this.decision = decision;
        }
    }

    /** One coordinate-free UTC history day. */
    public static final class HistoryDay {
        public final String day;
        @Json(name = "estimated_seconds") public final long estimatedSeconds;
        public final boolean corrected;
        @Json(name = "estimate_method") public final String estimateMethod;
        public final int revision;
        @Json(name = "corrected_by_display_name") public final String correctedByDisplayName;
        @Json(name = "correction_reason") public final String correctionReason;

        /** Creates a decoded history day. */
        public HistoryDay(String day, long estimatedSeconds, boolean corrected,
                String estimateMethod, int revision, String correctedByDisplayName,
                String correctionReason) {
            this.day = day;
            this.estimatedSeconds = estimatedSeconds;
            this.corrected = corrected;
            this.estimateMethod = estimateMethod;
            this.revision = revision;
            this.correctedByDisplayName = correctedByDisplayName;
            this.correctionReason = correctionReason;
        }
    }

    /** Optimistic correction to one completed UTC calendar day. */
    public static final class DayCorrection {
        @Json(name = "estimated_seconds") public final long estimatedSeconds;
        @Json(name = "expected_revision") public final int expectedRevision;
        public final String reason;

        /** Creates a bounded retry-safe daily correction. */
        public DayCorrection(long estimatedSeconds, int expectedRevision, String reason) {
            this.estimatedSeconds = estimatedSeconds;
            this.expectedRevision = expectedRevision;
            this.reason = reason;
        }
    }

    /** Coordinate-free acknowledgement after deterministic recomputation. */
    public static final class LocationBatchResult {
        public final int accepted;
        public final int duplicates;
        @Json(name = "nearby_seconds_recomputed") public final long nearbySecondsRecomputed;

        /** Creates a decoded location result. */
        public LocationBatchResult(int accepted, int duplicates, long nearbySecondsRecomputed) {
            this.accepted = accepted;
            this.duplicates = duplicates;
            this.nearbySecondsRecomputed = nearbySecondsRecomputed;
        }
    }
}
