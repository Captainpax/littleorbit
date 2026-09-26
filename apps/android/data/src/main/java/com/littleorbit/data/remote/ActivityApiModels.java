package com.littleorbit.data.remote;

import com.squareup.moshi.Json;
import java.util.List;

/** Privacy-minimized wire models for the in-app activity panel. */
public final class ActivityApiModels {
    private ActivityApiModels() {}

    /** One content-free event authorized to the active couple. */
    public static final class Event {
        public final String id;
        public final long sequence;
        public final String kind;
        @Json(name = "partner_display_name") public final String partnerDisplayName;
        @Json(name = "target_type") public final String targetType;
        @Json(name = "target_id") public final String targetId;
        @Json(name = "target_title") public final String targetTitle;
        public final String emoji;
        @Json(name = "created_at") public final String createdAt;
        public final boolean seen;

        /** Creates one decoded event without note or quiz content. */
        public Event(
                String id, long sequence, String kind, String partnerDisplayName,
                String targetType, String targetId, String targetTitle, String emoji,
                String createdAt, boolean seen) {
            this.id = id;
            this.sequence = sequence;
            this.kind = kind;
            this.partnerDisplayName = partnerDisplayName;
            this.targetType = targetType;
            this.targetId = targetId;
            this.targetTitle = targetTitle;
            this.emoji = emoji;
            this.createdAt = createdAt;
            this.seen = seen;
        }
    }

    /** One newest-first cursor page. */
    public static final class Page {
        public final List<Event> items;
        @Json(name = "next_cursor") public final Long nextCursor;
        @Json(name = "seen_through") public final long seenThrough;

        /** Creates a decoded page. */
        public Page(List<Event> items, Long nextCursor, long seenThrough) {
            this.items = items;
            this.nextCursor = nextCursor;
            this.seenThrough = seenThrough;
        }
    }

    /** Monotonic visible-event acknowledgement. */
    public static final class SeenRequest {
        @Json(name = "through_sequence") public final long throughSequence;
        @Json(name = "operation_id") public final String operationId;

        /** Creates one retry-safe seen watermark. */
        public SeenRequest(long throughSequence, String operationId) {
            this.throughSequence = throughSequence;
            this.operationId = operationId;
        }
    }
}
