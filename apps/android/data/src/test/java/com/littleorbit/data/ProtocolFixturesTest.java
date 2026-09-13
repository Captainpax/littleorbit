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
            "location-batch", "note-operation", "pairing", "question-batch", "orbit-profile", "smooch");
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
    public void rc10TogetherTimeUsesServerPairingAndEstimatedNearbyShapes() throws IOException {
        assertTrue(validTogetherTime(read("v3", "together-time.valid.json")));
        assertFalse(validTogetherTime(read("v3", "together-time.invalid.json")));
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
            case "location-batch" -> validLocation(value);
            case "note-operation" -> validNote(value);
            case "pairing" -> validPairing(value);
            case "question-batch" -> validQuestionBatch(value);
            case "orbit-profile" -> validOrbitProfile(value);
            case "smooch" -> validSmooch(value);
            default -> false;
        };
    }

    private static boolean validSmooch(Map<String, Object> value) {
        return value.size() == 2
                && isUuid(value.get("operation_id"))
                && List.of("😘", "😍", "🤭", "😈", "🔥", "👀", "💖", "🐻", "🍑")
                        .contains(value.get("emoji"));
    }

    private static boolean validTogetherTime(Map<String, Object> value) {
        return value.size() == 8
                && String.valueOf(value.get("paired_at")).matches("^.+T.+(?:Z|[+-].+)$")
                && numberIn(value.get("paired_days"), 0, Integer.MAX_VALUE)
                && numberIn(value.get("nearby_estimated_seconds"), 0, Integer.MAX_VALUE)
                && numberIn(value.get("proximity_threshold_m"), 10, 1000)
                && value.get("location_enabled_by_me") instanceof Boolean
                && value.get("location_enabled_by_both") instanceof Boolean
                && "estimate".equals(value.get("label"));
    }

    private static boolean validOrbitProfile(Map<String, Object> value) {
        if (value.size() != 2 || !(value.get("me") instanceof Map<?, ?> me)) return false;
        Object name = me.get("display_name");
        Object photo = me.get("photo");
        boolean validPhoto = photo == null || photo instanceof Map<?, ?> details
                && numberIn(details.get("revision"), 1, Integer.MAX_VALUE)
                && String.valueOf(details.get("sha256")).matches("^[a-f0-9]{64}$");
        return name instanceof String text && !text.isBlank() && validPhoto;
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
