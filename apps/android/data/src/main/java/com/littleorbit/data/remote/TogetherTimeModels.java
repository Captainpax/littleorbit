package com.littleorbit.data.remote;

import com.squareup.moshi.Json;

/** RC6 relationship-age and coordinate-free nearby-time HTTP DTOs. */
public final class TogetherTimeModels {
    private TogetherTimeModels() {}

    /** RC10 pair-age state derived from the immutable server pairing instant. */
    public static final class PairSummary {
        @Json(name = "paired_at") public final String pairedAt;
        @Json(name = "paired_days") public final long pairedDays;
        @Json(name = "nearby_estimated_seconds") public final long nearbyEstimatedSeconds;
        @Json(name = "nearby_last_processed_at") public final String nearbyLastProcessedAt;
        @Json(name = "nearby_confidence") public final String nearbyConfidence;
        @Json(name = "proximity_threshold_m") public final double proximityThresholdM;
        @Json(name = "location_enabled_by_me") public final boolean locationByMe;
        @Json(name = "location_enabled_by_both") public final boolean locationByBoth;
        public final String label;

        /** Creates one decoded privacy-limited pair and estimate summary. */
        public PairSummary(String pairedAt, long pairedDays, long nearbyEstimatedSeconds,
                String nearbyLastProcessedAt, String nearbyConfidence, double proximityThresholdM,
                boolean locationByMe, boolean locationByBoth, String label) {
            this.pairedAt = pairedAt;
            this.pairedDays = pairedDays;
            this.nearbyEstimatedSeconds = nearbyEstimatedSeconds;
            this.nearbyLastProcessedAt = nearbyLastProcessedAt;
            this.nearbyConfidence = nearbyConfidence;
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
        public final int revision;
        @Json(name = "corrected_by_display_name") public final String correctedByDisplayName;
        @Json(name = "correction_reason") public final String correctionReason;

        /** Creates a decoded history day. */
        public HistoryDay(String day, long estimatedSeconds, boolean corrected, int revision,
                String correctedByDisplayName, String correctionReason) {
            this.day = day;
            this.estimatedSeconds = estimatedSeconds;
            this.corrected = corrected;
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
