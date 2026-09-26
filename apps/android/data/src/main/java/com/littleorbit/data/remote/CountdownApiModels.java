package com.littleorbit.data.remote;

import com.squareup.moshi.Json;
import java.util.List;

/** Calendar-aware countdown contracts kept separate from general API metadata. */
public final class CountdownApiModels {
    private CountdownApiModels() {}

    /** Shared timed state with the caller's private reminder offsets. */
    public static final class Countdown {
        public final String id;
        public final String title;
        @Json(name = "occurs_at") public final String occursAt;
        public final String timezone;
        @Json(name = "timing_kind") public final String timingKind;
        @Json(name = "occurs_on") public final String occursOn;
        @Json(name = "my_reminder_offsets_minutes") public final List<Integer> reminderOffsets;
        public final String notes;
        public final int revision;
        @Json(name = "updated_at") public final String updatedAt;
        @Json(ignore = true) public final boolean pendingSync;
        @Json(ignore = true) public final boolean syncConflict;

        /** Creates backward-compatible timed state. */
        public Countdown(
                String id, String title, String occursAt, String timezone, String notes,
                int revision, String updatedAt) {
            this(id, title, occursAt, timezone, "timed", null, List.of(), notes,
                    revision, updatedAt, false, false);
        }

        /** Creates complete timed or all-day state. */
        public Countdown(
                String id, String title, String occursAt, String timezone,
                String timingKind, String occursOn, List<Integer> reminderOffsets,
                String notes, int revision, String updatedAt,
                boolean pendingSync, boolean syncConflict) {
            this.id = id; this.title = title; this.occursAt = occursAt;
            this.timezone = timezone; this.timingKind = timingKind;
            this.occursOn = occursOn;
            this.reminderOffsets = reminderOffsets == null ? List.of() : List.copyOf(reminderOffsets);
            this.notes = notes; this.revision = revision; this.updatedAt = updatedAt;
            this.pendingSync = pendingSync; this.syncConflict = syncConflict;
        }
    }

    /** Retry-safe timed or all-day mutation. */
    public static final class Mutation {
        @Json(name = "operation_id") public final String operationId;
        public final String title;
        @Json(name = "occurs_at") public final String occursAt;
        public final String timezone;
        @Json(name = "timing_kind") public final String timingKind;
        @Json(name = "occurs_on") public final String occursOn;
        public final String notes;
        @Json(name = "expected_revision") public final Integer expectedRevision;

        /** Creates a timed or all-day mutation. */
        public Mutation(
                String operationId, String title, String occursAt, String timezone,
                String timingKind, String occursOn, String notes, Integer expectedRevision) {
            this.operationId = operationId; this.title = title; this.occursAt = occursAt;
            this.timezone = timezone; this.timingKind = timingKind; this.occursOn = occursOn;
            this.notes = notes; this.expectedRevision = expectedRevision;
        }
    }

    /** Complete private reminder-offset replacement. */
    public static final class ReminderUpdate {
        @Json(name = "offsets_minutes") public final List<Integer> offsetsMinutes;

        /** Creates a bounded account-scoped reminder set. */
        public ReminderUpdate(List<Integer> offsetsMinutes) {
            this.offsetsMinutes = List.copyOf(offsetsMinutes);
        }
    }

    /** Retry-safe optimistic deletion. */
    public static final class DeleteRequest {
        @Json(name = "operation_id") public final String operationId;
        @Json(name = "expected_revision") public final int expectedRevision;

        /** Creates a deletion request. */
        public DeleteRequest(String operationId, int expectedRevision) {
            this.operationId = operationId;
            this.expectedRevision = expectedRevision;
        }
    }
}
