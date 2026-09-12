package com.littleorbit.data;

import static org.junit.Assert.assertFalse;
import static org.junit.Assert.assertTrue;

import com.squareup.moshi.JsonAdapter;
import com.squareup.moshi.Moshi;
import com.squareup.moshi.Types;
import java.io.IOException;
import java.lang.reflect.Type;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.charset.StandardCharsets;
import java.util.List;
import java.util.Map;
import java.util.UUID;
import org.junit.Test;

/** Cross-language smoke checks over the canonical protocol fixtures. */
public final class ProtocolFixturesTest {
    private static final List<String> NAMES = List.of(
            "location-batch", "note-operation", "pairing", "question-batch");
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
            default -> false;
        };
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
