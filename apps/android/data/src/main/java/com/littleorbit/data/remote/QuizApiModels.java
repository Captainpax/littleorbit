package com.littleorbit.data.remote;

import com.squareup.moshi.Json;
import java.util.List;
import java.util.Map;

/** RC5 quiz-only DTOs kept separate from legacy service models. */
public final class QuizApiModels {
    private QuizApiModels() {}

    /** Stable server-owned answer option. */
    public static final class Option {
        public final String id;
        public final String label;
        @Json(name = "icon_key") public final String iconKey;

        /** Creates one decoded option. */
        public Option(String id, String label, String iconKey) {
            this.id = id;
            this.label = label;
            this.iconKey = iconKey;
        }
    }

    /** One ordered question with only reveal-safe answer data. */
    public static final class Question {
        public final String id;
        public final int position;
        @Json(name = "interaction_version") public final int interactionVersion;
        public final String kind;
        public final String prompt;
        public final String category;
        public final boolean intimacy;
        public final List<Option> options;
        @Json(name = "scale_low_label") public final String scaleLowLabel;
        @Json(name = "scale_high_label") public final String scaleHighLabel;
        @Json(name = "my_answer") public final Map<String, Object> myAnswer;
        @Json(name = "my_answer_revision") public final int myAnswerRevision;
        @Json(name = "partner_answer") public final Map<String, Object> partnerAnswer;

        /** Creates one decoded question. */
        public Question(
                String id,
                int position,
                int interactionVersion,
                String kind,
                String prompt,
                String category,
                boolean intimacy,
                List<Option> options,
                String scaleLowLabel,
                String scaleHighLabel,
                Map<String, Object> myAnswer,
                int myAnswerRevision,
                Map<String, Object> partnerAnswer) {
            this.id = id;
            this.position = position;
            this.interactionVersion = interactionVersion;
            this.kind = kind;
            this.prompt = prompt;
            this.category = category;
            this.intimacy = intimacy;
            this.options = List.copyOf(options);
            this.scaleLowLabel = scaleLowLabel;
            this.scaleHighLabel = scaleHighLabel;
            this.myAnswer = myAnswer;
            this.myAnswerRevision = myAnswerRevision;
            this.partnerAnswer = partnerAnswer;
        }
    }

    /** Complete privacy-aware state for one UTC day. */
    public static final class Day {
        @Json(name = "quiz_date") public final String quizDate;
        public final String status;
        public final int revision;
        @Json(name = "my_finished") public final boolean myFinished;
        @Json(name = "partner_finished") public final boolean partnerFinished;
        public final boolean revealed;
        public final boolean editable;
        public final List<Question> questions;

        /** Creates a decoded quiz day. */
        public Day(
                String quizDate,
                String status,
                int revision,
                boolean myFinished,
                boolean partnerFinished,
                boolean revealed,
                boolean editable,
                List<Question> questions) {
            this.quizDate = quizDate;
            this.status = status;
            this.revision = revision;
            this.myFinished = myFinished;
            this.partnerFinished = partnerFinished;
            this.revealed = revealed;
            this.editable = editable;
            this.questions = List.copyOf(questions);
        }
    }

    /** Retry-safe private draft mutation. */
    public static final class DraftMutation {
        @Json(name = "operation_id") public final String operationId;
        @Json(name = "expected_revision") public final int expectedRevision;
        public final Map<String, Object> answer;

        /** Creates a draft mutation. */
        public DraftMutation(String operationId, int expectedRevision, Map<String, Object> answer) {
            this.operationId = operationId;
            this.expectedRevision = expectedRevision;
            this.answer = Map.copyOf(answer);
        }
    }

    /** Retry-safe finish or reopen mutation. */
    public static final class DayMutation {
        @Json(name = "operation_id") public final String operationId;
        @Json(name = "expected_day_revision") public final int expectedDayRevision;

        /** Creates a day mutation. */
        public DayMutation(String operationId, int expectedDayRevision) {
            this.operationId = operationId;
            this.expectedDayRevision = expectedDayRevision;
        }
    }

    /** Content-free history row. */
    public static final class HistoryItem {
        @Json(name = "quiz_date") public final String quizDate;
        public final String status;
        @Json(name = "answered_count") public final int answeredCount;
        @Json(name = "custom_count") public final int customCount;

        /** Creates a history item. */
        public HistoryItem(String quizDate, String status, int answeredCount, int customCount) {
            this.quizDate = quizDate;
            this.status = status;
            this.answeredCount = answeredCount;
            this.customCount = customCount;
        }
    }

    /** Content-free polling state. */
    public static final class Status {
        @Json(name = "quiz_date") public final String quizDate;
        @Json(name = "state_version") public final int stateVersion;
        @Json(name = "my_finished") public final boolean myFinished;
        @Json(name = "partner_finished") public final boolean partnerFinished;
        public final boolean revealed;

        /** Creates decoded polling state. */
        public Status(
                String quizDate,
                int stateVersion,
                boolean myFinished,
                boolean partnerFinished,
                boolean revealed) {
            this.quizDate = quizDate;
            this.stateVersion = stateVersion;
            this.myFinished = myFinished;
            this.partnerFinished = partnerFinished;
            this.revealed = revealed;
        }
    }

    /** Guided custom-question mutation. */
    public static final class CustomMutation {
        public final String kind;
        public final String prompt;
        public final String category;
        public final boolean intimacy;
        public final List<Option> options;
        @Json(name = "scale_low_label") public final String scaleLowLabel;
        @Json(name = "scale_high_label") public final String scaleHighLabel;
        public final boolean surprise;

        /** Creates a validated custom mutation. */
        public CustomMutation(
                String kind,
                String prompt,
                String category,
                boolean intimacy,
                List<Option> options,
                String scaleLowLabel,
                String scaleHighLabel,
                boolean surprise) {
            this.kind = kind;
            this.prompt = prompt;
            this.category = category;
            this.intimacy = intimacy;
            this.options = List.copyOf(options);
            this.scaleLowLabel = scaleLowLabel;
            this.scaleHighLabel = scaleHighLabel;
            this.surprise = surprise;
        }
    }

    /** Creator-visible queued custom question. */
    public static final class CustomQuestion {
        public final String id;
        @Json(name = "publish_date") public final String publishDate;
        @Json(name = "custom_slot") public final int customSlot;
        public final String prompt;
        public final String kind;
        public final String category;
        public final boolean surprise;

        /** Creates decoded custom queue metadata. */
        public CustomQuestion(
                String id,
                String publishDate,
                int customSlot,
                String prompt,
                String kind,
                String category,
                boolean surprise) {
            this.id = id;
            this.publishDate = publishDate;
            this.customSlot = customSlot;
            this.prompt = prompt;
            this.kind = kind;
            this.category = category;
            this.surprise = surprise;
        }
    }

    /** Privacy-limited custom queue response. */
    public static final class CustomQueue {
        public final List<CustomQuestion> mine;
        public final List<CustomQuestion> shared;
        @Json(name = "partner_surprise_count") public final int partnerSurpriseCount;

        /** Creates a custom queue response. */
        public CustomQueue(
                List<CustomQuestion> mine,
                List<CustomQuestion> shared,
                int partnerSurpriseCount) {
            this.mine = List.copyOf(mine);
            this.shared = List.copyOf(shared);
            this.partnerSurpriseCount = partnerSurpriseCount;
        }
    }

    /** Structured hide/report request. */
    public static final class ReportMutation {
        @Json(name = "reason_code") public final String reasonCode;
        public final String details;

        /** Creates a report mutation. */
        public ReportMutation(String reasonCode, String details) {
            this.reasonCode = reasonCode;
            this.details = details;
        }
    }
}
