package com.littleorbit.data;

import static org.junit.Assert.assertFalse;
import static org.junit.Assert.assertTrue;

import com.squareup.moshi.JsonAdapter;
import com.squareup.moshi.Moshi;
import com.squareup.moshi.Types;
import java.io.IOException;
import java.lang.reflect.Type;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.List;
import java.util.Map;
import java.util.UUID;
import org.junit.Test;

/** Cross-language smoke checks over the canonical protocol fixtures. */
public final class ProtocolFixturesTest {
    private static final List<String> NAMES = List.of(
            "activity-page", "countdown", "location-batch", "note-operation", "note-attachment",
            "notification-event", "pairing",
            "question-batch", "orbit-profile", "partner-name", "smooch");
    private final JsonAdapter<Map<String, Object>> adapter;

    /** Creates a generic JSON adapter without coupling protocol payloads to Room entities. */
    public ProtocolFixturesTest() {
        Type type = Types.newParameterizedType(Map.class, String.class, Object.class);
        adapter = new Moshi.Builder().build().adapter(type);
    }

    @Test
    public void canonicalFixturesKeepExpectedValidAndInvalidShapes() throws IOException {
        for (String name : NAMES) {
            assertTrue(name, hasValidShape(name, read("v1", name + ".valid.json")));
            assertFalse(name, hasValidShape(name, read("v1", name + ".invalid.json")));
        }
    }

    @Test
    public void rc5QuizFixturesKeepTypedAnswerAndPrivacyShapes() throws IOException {
        assertTrue(validQuestionBatchV2(read("v2", "question-batch.valid.json")));
        assertFalse(validQuestionBatchV2(read("v2", "question-batch.invalid.json")));
        assertTrue(validQuizDay(read("v2", "quiz-day.valid.json")));
        assertFalse(validQuizDay(read("v2", "quiz-day.invalid.json")));
    }

    @Test
    public void v3TogetherTimeUsesBoundedLiveEstimateShape() throws IOException {
        assertTrue(validTogetherTime(read("v3", "together-time.valid.json")));
        assertFalse(validTogetherTime(read("v3", "together-time.invalid.json")));
        assertTrue(validLocationV3(read("v3", "location-batch.valid.json")));
        assertFalse(validLocationV3(read("v3", "location-batch.invalid.json")));
    }

    @Test
    public void v3QuestionBatchRequiresSemanticConceptIdentity() throws IOException {
        assertTrue(validQuestionBatchV3(read("v3", "question-batch.valid.json")));
        assertFalse(validQuestionBatchV3(read("v3", "question-batch.invalid.json")));
    }

    @Test
    public void releaseHistoryFixturesKeepPublicMetadataShape() throws IOException {
        assertTrue(validReleaseHistory(readList("release-history.valid.json")));
        assertFalse(validReleaseHistory(readList("release-history.invalid.json")));
    }

    private Map<String, Object> read(String version, String filename) throws IOException {
        Path fixture = repositoryRoot()
                .resolve("protocol/fixtures")
                .resolve(version)
                .resolve(filename);
        String json = new String(Files.readAllBytes(fixture), StandardCharsets.UTF_8);
        Map<String, Object> parsed = adapter.fromJson(json);
        if (parsed == null) {
            throw new IOException("Fixture is not a JSON object: " + filename);
        }
        return parsed;
    }

    private List<Map<String, Object>> readList(String filename) throws IOException {
        Path fixture = repositoryRoot().resolve("protocol/fixtures/v1").resolve(filename);
        Type type = Types.newParameterizedType(
                List.class, Types.newParameterizedType(Map.class, String.class, Object.class));
        JsonAdapter<List<Map<String, Object>>> listAdapter =
                new Moshi.Builder().build().adapter(type);
        List<Map<String, Object>> result = listAdapter.fromJson(
                new String(Files.readAllBytes(fixture), StandardCharsets.UTF_8));
        if (result == null) throw new IOException("Fixture is not a JSON list");
        return result;
    }

    private static Path repositoryRoot() throws IOException {
        Path current = Path.of("").toAbsolutePath();
        while (current != null && !Files.isDirectory(current.resolve("protocol/schemas/v1"))) {
            current = current.getParent();
        }
        if (current == null) {
            throw new IOException("Repository protocol directory was not found");
        }
        return current;
    }

    private static boolean hasValidShape(String name, Map<String, Object> value) {
        return switch (name) {
            case "activity-page" -> validActivityPage(value);
            case "countdown" -> validCountdown(value);
            case "location-batch" -> validLocation(value);
            case "note-operation" -> validNote(value);
            case "note-attachment" -> validAttachment(value);
            case "notification-event" -> validNotificationEvent(value);
            case "pairing" -> validPairing(value);
            case "question-batch" -> validQuestionBatch(value);
            case "orbit-profile" -> validOrbitProfile(value);
            case "partner-name" -> validPartnerName(value);
            case "smooch" -> validSmooch(value);
            default -> false;
        };
    }

    private static boolean validCountdown(Map<String, Object> value) {
        Object occursOn = value.get("occurs_on");
        boolean allDay = "all_day".equals(value.get("timing_kind"));
        if (value.size() != 10 || !isUuid(value.get("id"))
                || !boundedText(value.get("title"), 120)
                || !boundedText(value.get("timezone"), 64)
                || !(value.get("occurs_at") instanceof String instant)
                || !instant.matches("^.+T.+(?:Z|[+-].+)$")
                || !(value.get("my_reminder_offsets_minutes") instanceof List<?> reminders)
                || reminders.size() > 4
                || !reminders.stream().allMatch(List.of(0.0, 60.0, 1440.0, 10080.0)::contains)
                || !(value.get("notes") instanceof String notes) || notes.length() > 1000
                || !numberIn(value.get("revision"), 0, Integer.MAX_VALUE)) return false;
        return allDay
                ? occursOn instanceof String date && date.matches("^\\d{4}-\\d{2}-\\d{2}$")
                : occursOn == null;
    }

    private static boolean validActivityPage(Map<String, Object> value) {
        Object cursor = value.get("next_cursor");
        if (value.size() != 3
                || !numberIn(value.get("seen_through"), 0, Integer.MAX_VALUE)
                || !(cursor == null || numberIn(cursor, 1, Integer.MAX_VALUE))
                || !(value.get("items") instanceof List<?> items)
                || items.size() > 100) {
            return false;
        }
        return items.stream().allMatch(item -> item instanceof Map<?, ?> event
                && validActivityEvent(event));
    }

    private static boolean validActivityEvent(Map<?, ?> event) {
        Object targetId = event.get("target_id");
        Object targetTitle = event.get("target_title");
        return event.size() == 10
                && isUuid(event.get("id"))
                && numberIn(event.get("sequence"), 1, Integer.MAX_VALUE)
                && List.of("note_created", "note_updated", "attachment_available",
                        "countdown_created", "countdown_updated", "quiz_submitted",
                        "quiz_revealed", "smooch_received",
                        "relationship_name_changed").contains(event.get("kind"))
                && boundedText(event.get("partner_display_name"), 120)
                && (event.get("target_type") == null || List.of(
                        "note", "countdown", "quiz", "smooch").contains(event.get("target_type")))
                && (targetId == null || isUuid(targetId))
                && (targetTitle == null || boundedText(targetTitle, 120))
                && (event.get("emoji") == null || List.of(
                        "😘", "😍", "🤭", "😈", "🔥", "👀", "💖", "🐻", "🍑")
                        .contains(event.get("emoji")))
                && event.get("created_at") instanceof String instant
                && instant.matches("^.+T.+(?:Z|[+-].+)$")
                && event.get("seen") instanceof Boolean;
    }

    private static boolean boundedText(Object value, int maximum) {
        return value instanceof String text && !text.isBlank() && text.length() <= maximum;
    }

    private static boolean validSmooch(Map<String, Object> value) {
        return value.size() == 2
                && isUuid(value.get("operation_id"))
                && List.of("😘", "😍", "🤭", "😈", "🔥", "👀", "💖", "🐻", "🍑")
                        .contains(value.get("emoji"));
    }

    private static boolean validNotificationEvent(Map<String, Object> value) {
        if (value.size() != 12 || !isUuid(value.get("id"))
                || !(value.get("created_at") instanceof String created)
                || !(value.get("expires_at") instanceof String expires)
                || !created.matches("^.+T.+(?:Z|[+-].+)$")
                || !expires.matches("^.+T.+(?:Z|[+-].+)$")) return false;
        if ("note_editing".equals(value.get("kind"))) {
            return isUuid(value.get("note_id"))
                    && value.get("emoji") == null && value.get("phrase_key") == null
                    && noCountdownOrQuiz(value);
        }
        if ("smooch_received".equals(value.get("kind"))) {
            return List.of("😘", "😍", "🤭", "😈", "🔥", "👀", "💖", "🐻", "🍑")
                            .contains(value.get("emoji"))
                    && value.get("phrase_key") instanceof String
                    && value.get("note_id") == null && value.get("note_title") == null
                    && noCountdownOrQuiz(value);
        }
        if (List.of("countdown_created", "countdown_rescheduled").contains(value.get("kind"))) {
            return isUuid(value.get("countdown_id"))
                    && boundedText(value.get("countdown_title"), 120)
                    && noNoteOrQuiz(value);
        }
        return List.of("quiz_available", "quiz_partner_finished", "quiz_results_ready")
                        .contains(value.get("kind"))
                && String.valueOf(value.get("quiz_date")).matches("^\\d{4}-\\d{2}-\\d{2}$")
                && value.get("countdown_id") == null && value.get("countdown_title") == null
                && value.get("note_id") == null && value.get("note_title") == null;
    }

    private static boolean noCountdownOrQuiz(Map<String, Object> value) {
        return value.get("countdown_id") == null && value.get("countdown_title") == null
                && value.get("quiz_date") == null;
    }

    private static boolean noNoteOrQuiz(Map<String, Object> value) {
        return value.get("note_id") == null && value.get("note_title") == null
                && value.get("quiz_date") == null;
    }

    private static boolean validAttachment(Map<String, Object> value) {
        return value.size() == 5
                && isUuid(value.get("operation_id"))
                && value.get("file_name") instanceof String name
                && !name.isBlank()
                && !name.contains("..")
                && List.of("image/jpeg", "image/png", "image/webp", "image/gif",
                        "application/pdf", "text/plain", "text/markdown", "audio/mpeg",
                        "audio/mp4", "audio/ogg", "video/mp4", "video/webm")
                        .contains(value.get("media_type"))
                && numberIn(value.get("size_bytes"), 1, 104_857_600)
                && String.valueOf(value.get("sha256")).matches("^[a-f0-9]{64}$");
    }

    private static boolean validTogetherTime(Map<String, Object> value) {
        if (value.size() != 19
                || !isUuid(value.get("relationship_id"))
                || !(value.get("home_timezone") instanceof String zone)
                || zone.isBlank() || zone.length() > 64
                || !String.valueOf(value.get("paired_at")).matches("^.+T.+(?:Z|[+-].+)$")
                || !numberIn(value.get("paired_days"), 0, Integer.MAX_VALUE)
                || !numberIn(value.get("nearby_observed_seconds"), 0, Integer.MAX_VALUE)
                || !numberIn(value.get("nearby_estimated_seconds"), 0, Integer.MAX_VALUE)
                || !numberIn(value.get("nearby_provisional_seconds"), 0, 300)
                || !instantOrNull(value.get("counting_anchor_at"))
                || !instantOrNull(value.get("counting_live_until"))
                || !instantOrNull(value.get("nearby_last_processed_at"))) return false;
        return String.valueOf(value.get("server_now")).matches("^.+T.+(?:Z|[+-].+)$")
                && List.of("sharing_disabled", "waiting_for_partner", "confirming", "nearby",
                        "apart", "poor_accuracy", "stale").contains(value.get("counting_state"))
                && List.of("unavailable", "low", "medium", "high")
                        .contains(value.get("nearby_confidence"))
                && numberIn(value.get("algorithm_version"), 4, Integer.MAX_VALUE)
                && value.get("includes_legacy_estimates") instanceof Boolean
                && numberIn(value.get("proximity_threshold_m"), 10, 1000)
                && value.get("location_enabled_by_me") instanceof Boolean
                && value.get("location_enabled_by_both") instanceof Boolean
                && "estimate".equals(value.get("label"));
    }

    private static boolean validLocationV3(Map<String, Object> value) {
        if (value.size() != 2 || !isUuid(value.get("relationship_id"))
                || !(value.get("samples") instanceof List<?> samples)
                || samples.isEmpty() || samples.size() > 48) return false;
        return samples.stream().allMatch(item -> item instanceof Map<?, ?> sample
                && sample.size() == 5 && isUuid(sample.get("sample_id"))
                && String.valueOf(sample.get("recorded_at")).matches("^.+T.+(?:Z|[+-].+)$")
                && numberIn(sample.get("latitude"), -90, 90)
                && numberIn(sample.get("longitude"), -180, 180)
                && numberIn(sample.get("accuracy_m"), 1, 1000));
    }

    private static boolean instantOrNull(Object value) {
        return value == null || String.valueOf(value).matches("^.+T.+(?:Z|[+-].+)$");
    }

    private static boolean validOrbitProfile(Map<String, Object> value) {
        if (value.size() != 2 || !(value.get("me") instanceof Map<?, ?> me)) return false;
        Object name = me.get("display_name");
        Object photo = me.get("photo");
        boolean validPhoto = photo == null || photo instanceof Map<?, ?> details
                && numberIn(details.get("revision"), 1, Integer.MAX_VALUE)
                && String.valueOf(details.get("sha256")).matches("^[a-f0-9]{64}$");
        return name instanceof String text && !text.isBlank()
                && numberIn(me.get("name_revision"), 0, Integer.MAX_VALUE)
                && me.get("partner_assigned") instanceof Boolean
                && validPhoto;
    }

    private static boolean validPartnerName(Map<String, Object> value) {
        Object assigned = value.get("assigned_name");
        return value.size() == 5
                && boundedText(value.get("display_name"), 80)
                && (assigned == null || boundedText(assigned, 40))
                && numberIn(value.get("revision"), 1, Integer.MAX_VALUE)
                && value.get("partner_assigned") instanceof Boolean
                && String.valueOf(value.get("updated_at")).matches("^.+T.+(?:Z|[+-].+)$");
    }

    private static boolean validReleaseHistory(List<Map<String, Object>> values) {
        return !values.isEmpty() && values.stream().allMatch(item ->
                item.get("version") instanceof String version && !version.isBlank()
                && numberIn(item.get("version_code"), 1, Integer.MAX_VALUE)
                && String.valueOf(item.get("github_release_url")).startsWith("https://")
                && String.valueOf(item.get("sha256")).matches("^[a-f0-9]{64}$")
                && numberIn(item.get("minimum_android"), 29, Integer.MAX_VALUE)
                && item.get("release_notes") instanceof String notes && !notes.isBlank());
    }

    private static boolean validLocation(Map<String, Object> value) {
        Object samples = value.get("samples");
        if (!(samples instanceof List<?> list)
                || list.isEmpty()
                || list.size() > 48
                || value.size() != 1
                || !(list.get(0) instanceof Map<?, ?> sample)) {
            return false;
        }
        return isUuid(sample.get("sample_id"))
                && numberIn(sample.get("latitude"), -90, 90)
                && numberIn(sample.get("longitude"), -180, 180)
                && numberIn(sample.get("accuracy_m"), Double.MIN_VALUE, 1000);
    }

    private static boolean validNote(Map<String, Object> value) {
        boolean base = numberIn(value.get("base_revision"), 0, Integer.MAX_VALUE);
        boolean position = numberIn(value.get("position"), 0, Integer.MAX_VALUE);
        String kind = String.valueOf(value.get("kind"));
        boolean edit = "insert".equals(kind)
                ? value.get("text") instanceof String text && !text.isEmpty() && !value.containsKey("length")
                : "delete".equals(kind)
                        && numberIn(value.get("length"), 1, 4000)
                        && !value.containsKey("text");
        return value.size() == 5 && isUuid(value.get("operation_id")) && base && position && edit;
    }

    private static boolean validPairing(Map<String, Object> value) {
        Object code = value.get("code");
        return value.size() == 1
                && code instanceof String text
                && text.matches("^[ABCDEFGHJKLMNPQRSTUVWXYZ23456789]{8}$");
    }

    private static boolean validQuestionBatch(Map<String, Object> value) {
        Object questions = value.get("questions");
        if (!(questions instanceof List<?> list) || list.size() < 5 || list.size() > 12) {
            return false;
        }
        return list.stream().allMatch(item -> item instanceof Map<?, ?> question
                && question.get("prompt") instanceof String prompt
                && prompt.length() >= 12);
    }

    private static boolean validQuestionBatchV2(Map<String, Object> value) {
        Object questions = value.get("questions");
        if (!"2".equals(value.get("schema_version"))
                || !(questions instanceof List<?> list)
                || list.size() != 10) {
            return false;
        }
        return list.stream().allMatch(item -> item instanceof Map<?, ?> question
                && question.get("prompt") instanceof String prompt
                && prompt.length() >= 12
                && question.get("options") instanceof List<?> options
                && question.get("option_icons") instanceof List<?> icons
                && options.size() == icons.size());
    }

    private static boolean validQuestionBatchV3(Map<String, Object> value) {
        Object questions = value.get("questions");
        if (!"3".equals(value.get("schema_version"))
                || !(questions instanceof List<?> list)
                || list.size() != 10) {
            return false;
        }
        return list.stream().allMatch(item -> item instanceof Map<?, ?> question
                && question.get("prompt") instanceof String prompt
                && prompt.length() >= 12
                && question.get("concept_family") instanceof String family
                && family.matches("^[a-z0-9-]{3,80}$")
                && boundedText(question.get("concept_summary"), 180)
                && question.get("options") instanceof List<?> options
                && question.get("option_icons") instanceof List<?> icons
                && options.size() == icons.size());
    }

    private static boolean validQuizDay(Map<String, Object> value) {
        Object questions = value.get("questions");
        if (!(questions instanceof List<?> list)
                || list.size() != 5
                || !numberIn(value.get("revision"), 0, Integer.MAX_VALUE)) {
            return false;
        }
        boolean revealed = Boolean.TRUE.equals(value.get("revealed"));
        return list.stream().allMatch(item -> item instanceof Map<?, ?> question
                && numberIn(question.get("position"), 1, 5)
                && numberIn(question.get("interaction_version"), 2, 2)
                && (revealed || question.get("partner_answer") == null));
    }

    private static boolean isUuid(Object value) {
        try {
            UUID.fromString(String.valueOf(value));
            return true;
        } catch (IllegalArgumentException invalid) {
            return false;
        }
    }

    private static boolean numberIn(Object value, double minimum, double maximum) {
        return value instanceof Number number
                && number.doubleValue() >= minimum
                && number.doubleValue() <= maximum;
    }
}
