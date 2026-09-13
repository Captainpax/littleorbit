package com.littleorbit.data.remote;

import com.squareup.moshi.Json;
import java.util.List;
import java.util.Map;

/** Versioned Smooch requests and privacy-limited responses. */
public final class SmoochApiModels {
    private SmoochApiModels() {}

    /** Retry-safe fixed-emoji send request. */
    public static final class SendRequest {
        @Json(name = "operation_id") public final String operationId;
        public final String emoji;

        /** Creates one send attempt whose operation ID survives retries. */
        public SendRequest(String operationId, String emoji) {
            this.operationId = operationId;
            this.emoji = emoji;
        }
    }

    /** Acknowledged send state. */
    public static final class Sent {
        public final String id;
        public final String emoji;
        @Json(name = "phrase_key") public final String phraseKey;
        @Json(name = "partner_display_name") public final String partnerName;
        @Json(name = "sent_at") public final String sentAt;
        @Json(name = "remaining_this_hour") public final int remaining;

        /** Creates a decoded send acknowledgement. */
        public Sent(String id, String emoji, String phraseKey, String partnerName,
                String sentAt, int remaining) {
            this.id = id;
            this.emoji = emoji;
            this.phraseKey = phraseKey;
            this.partnerName = partnerName;
            this.sentAt = sentAt;
            this.remaining = remaining;
        }
    }

    /** Pending partner notification. */
    public static final class Delivery {
        public final String id;
        public final String emoji;
        @Json(name = "phrase_key") public final String phraseKey;
        @Json(name = "partner_display_name") public final String partnerName;
        @Json(name = "sent_at") public final String sentAt;

        /** Creates a decoded delivery. */
        public Delivery(String id, String emoji, String phraseKey, String partnerName,
                String sentAt) {
            this.id = id;
            this.emoji = emoji;
            this.phraseKey = phraseKey;
            this.partnerName = partnerName;
            this.sentAt = sentAt;
        }
    }

    /** Bounded delivery acknowledgement. */
    public static final class DeliveryAck {
        @Json(name = "smooch_ids") public final List<String> ids;

        /** Creates an immutable acknowledged-ID request. */
        public DeliveryAck(List<String> ids) { this.ids = List.copyOf(ids); }
    }

    /** Calendar-week totals and per-emoji distribution. */
    public static final class Week {
        @Json(name = "week_start") public final String weekStart;
        @Json(name = "week_end") public final String weekEnd;
        public final int sent;
        public final int received;
        public final int combined;
        @Json(name = "emoji_counts") public final Map<String, Integer> emojiCounts;

        /** Creates an immutable decoded week. */
        public Week(String weekStart, String weekEnd, int sent, int received,
                int combined, Map<String, Integer> emojiCounts) {
            this.weekStart = weekStart;
            this.weekEnd = weekEnd;
            this.sent = sent;
            this.received = received;
            this.combined = combined;
            this.emojiCounts = Map.copyOf(emojiCounts);
        }
    }

    /** Current send capacity and shared weekly recap. */
    public static final class Status {
        @Json(name = "partner_display_name") public final String partnerName;
        @Json(name = "remaining_this_hour") public final int remaining;
        @Json(name = "current_week") public final Week currentWeek;

        /** Creates decoded dedicated-tab state. */
        public Status(String partnerName, int remaining, Week currentWeek) {
            this.partnerName = partnerName;
            this.remaining = remaining;
            this.currentWeek = currentWeek;
        }
    }
}
