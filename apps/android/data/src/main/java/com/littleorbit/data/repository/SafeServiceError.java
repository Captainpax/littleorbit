package com.littleorbit.data.repository;

import com.squareup.moshi.JsonAdapter;
import com.squareup.moshi.Moshi;
import java.io.IOException;
import java.io.Reader;
import java.util.Map;
import retrofit2.Response;

/** Parses only allowlisted, content-free service error codes from bounded response bodies. */
public final class SafeServiceError {
    private static final int MAX_ERROR_CHARS = 4096;
    private static final JsonAdapter<Map> ERROR_JSON =
            new Moshi.Builder().build().adapter(Map.class);

    private SafeServiceError() {}

    /** Returns true only for the exact structured inactive-relationship response. */
    public static boolean relationshipInactive(Response<?> response) {
        return response.code() == 409
                && "relationship_inactive".equals(safeCode(response.code(), readError(response)));
    }

    static String code(Response<?> response) {
        return safeCode(response.code(), readError(response));
    }

    static String safeCode(int statusCode, String payload) {
        if (statusCode != 409 || payload.isBlank()) return null;
        try {
            Map<?, ?> root = ERROR_JSON.fromJson(payload);
            Object detail = root == null ? null : root.get("detail");
            if (!(detail instanceof Map<?, ?> object)) return null;
            return "relationship_inactive".equals(object.get("code"))
                    ? "relationship_inactive" : null;
        } catch (IOException | RuntimeException failure) {
            return null;
        }
    }

    private static String readError(Response<?> response) {
        okhttp3.ResponseBody body = response.errorBody();
        if (body == null) return "";
        try (Reader reader = body.charStream()) {
            char[] buffer = new char[MAX_ERROR_CHARS + 1];
            int total = 0;
            for (int count; total < buffer.length
                    && (count = reader.read(buffer, total, buffer.length - total)) >= 0; ) {
                total += count;
            }
            return total > MAX_ERROR_CHARS ? "" : new String(buffer, 0, total);
        } catch (IOException failure) {
            return "";
        }
    }
}
