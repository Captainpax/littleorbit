package com.littleorbit.data.remote;

import com.squareup.moshi.Json;
import java.util.List;

/** Versioned self-hosted notification preferences, devices, and event payloads. */
public final class NotificationApiModels {
    private NotificationApiModels() {}

    /** Complete account-wide preference state. */
    public static final class Preferences {
        @Json(name = "master_enabled") public final boolean master;
        @Json(name = "smooches_enabled") public final boolean smooches;
        @Json(name = "note_editing_enabled") public final boolean noteEditing;
        @Json(name = "daily_quiz_enabled") public final boolean dailyQuiz;
        @Json(name = "countdowns_enabled") public final boolean countdowns;
        @Json(name = "weekly_summary_enabled") public final boolean weeklySummary;
        @Json(name = "updated_at") public final String updatedAt;

        /** Creates decoded or complete replacement preference state. */
        public Preferences(
                boolean master, boolean smooches, boolean noteEditing,
                boolean dailyQuiz, boolean countdowns, boolean weeklySummary,
                String updatedAt) {
            this.master = master;
            this.smooches = smooches;
            this.noteEditing = noteEditing;
            this.dailyQuiz = dailyQuiz;
            this.countdowns = countdowns;
            this.weeklySummary = weeklySummary;
            this.updatedAt = updatedAt;
        }

    }

    /** Complete preference replacement without response-only fields. */
    public static final class PreferencesUpdate {
        @Json(name = "master_enabled") public final boolean master;
        @Json(name = "smooches_enabled") public final boolean smooches;
        @Json(name = "note_editing_enabled") public final boolean noteEditing;
        @Json(name = "daily_quiz_enabled") public final boolean dailyQuiz;
        @Json(name = "countdowns_enabled") public final boolean countdowns;
        @Json(name = "weekly_summary_enabled") public final boolean weeklySummary;

        /** Copies editable state from a decoded preference response. */
        public PreferencesUpdate(Preferences value) {
            master = value.master;
            smooches = value.smooches;
            noteEditing = value.noteEditing;
            dailyQuiz = value.dailyQuiz;
            countdowns = value.countdowns;
            weeklySummary = value.weeklySummary;
        }

        /** Creates a complete preference replacement. */
        public PreferencesUpdate(
                boolean master, boolean smooches, boolean noteEditing,
                boolean dailyQuiz, boolean countdowns, boolean weeklySummary) {
            this.master = master;
            this.smooches = smooches;
            this.noteEditing = noteEditing;
            this.dailyQuiz = dailyQuiz;
            this.countdowns = countdowns;
            this.weeklySummary = weeklySummary;
        }
    }

    /** Authenticated installation heartbeat. */
    public static final class DeviceUpsert {
        public final String platform = "android";
        @Json(name = "app_version_code") public final int appVersionCode;
        @Json(name = "notifications_enabled") public final boolean notificationsEnabled;

        /** Creates one non-hardware device heartbeat. */
        public DeviceUpsert(int appVersionCode, boolean notificationsEnabled) {
            this.appVersionCode = appVersionCode;
            this.notificationsEnabled = notificationsEnabled;
        }
    }

    /** Registered installation state. */
    public static final class Device {
        @Json(name = "device_id") public final String deviceId;
        @Json(name = "last_seen_at") public final String lastSeenAt;
        @Json(name = "notifications_enabled") public final boolean notificationsEnabled;

        /** Creates decoded registration state. */
        public Device(String deviceId, String lastSeenAt, boolean notificationsEnabled) {
            this.deviceId = deviceId;
            this.lastSeenAt = lastSeenAt;
            this.notificationsEnabled = notificationsEnabled;
        }
    }

    /** One authorized partner, countdown, or quiz alert. */
    public static final class Event {
        public final String id;
        public final String kind;
        @Json(name = "created_at") public final String createdAt;
        @Json(name = "expires_at") public final String expiresAt;
        @Json(name = "actor_display_name") public final String actorName;
        public final String emoji;
        @Json(name = "phrase_key") public final String phraseKey;
        @Json(name = "note_id") public final String noteId;
        @Json(name = "note_title") public final String noteTitle;
        @Json(name = "countdown_id") public final String countdownId;
        @Json(name = "countdown_title") public final String countdownTitle;
        @Json(name = "quiz_date") public final String quizDate;

        /** Creates decoded privacy-limited event metadata. */
        public Event(
                String id, String kind, String createdAt, String expiresAt,
                String actorName, String emoji, String phraseKey,
                String noteId, String noteTitle,
                String countdownId, String countdownTitle, String quizDate) {
            this.id = id;
            this.kind = kind;
            this.createdAt = createdAt;
            this.expiresAt = expiresAt;
            this.actorName = actorName;
            this.emoji = emoji;
            this.phraseKey = phraseKey;
            this.noteId = noteId;
            this.noteTitle = noteTitle;
            this.countdownId = countdownId;
            this.countdownTitle = countdownTitle;
            this.quizDate = quizDate;
        }
    }

    /** Per-device acknowledgement after Android posts events. */
    public static final class DeliveryAck {
        @Json(name = "device_id") public final String deviceId;
        @Json(name = "event_ids") public final List<String> eventIds;

        /** Creates an immutable bounded acknowledgement request. */
        public DeliveryAck(String deviceId, List<String> eventIds) {
            this.deviceId = deviceId;
            this.eventIds = List.copyOf(eventIds);
        }
    }
}
