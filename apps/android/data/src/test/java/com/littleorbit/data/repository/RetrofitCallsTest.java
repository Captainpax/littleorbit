package com.littleorbit.data.repository;

import static org.junit.Assert.assertEquals;
import static org.junit.Assert.assertFalse;
import static org.junit.Assert.assertNull;
import static org.junit.Assert.assertTrue;

import okhttp3.MediaType;
import okhttp3.ResponseBody;
import org.junit.Test;
import retrofit2.Response;

/** Privacy-safe parsing checks for structured service failures. */
public final class RetrofitCallsTest {
    @Test
    public void acceptsOnlyExactStructuredRelationshipCode() {
        String body = "{\"detail\":{\"code\":\"relationship_inactive\","
                + "\"message\":\"Pair with a partner first\"}}";

        assertEquals("relationship_inactive", SafeServiceError.safeCode(409, body));
        assertNull(SafeServiceError.safeCode(400, body));
    }

    @Test
    public void rejectsMalformedOrMessageOnlyPayloads() {
        assertNull(SafeServiceError.safeCode(
                409, "{\"detail\":\"relationship_inactive\"}"));
        assertNull(SafeServiceError.safeCode(
                409, "{\"detail\":{\"message\":\"relationship_inactive\"}}"));
        assertNull(SafeServiceError.safeCode(409, "not-json"));
    }

    @Test
    public void responseParserRejectsGenericAndOversizedConflicts() {
        String exact = "{\"detail\":{\"code\":\"relationship_inactive\"}}";

        assertTrue(SafeServiceError.relationshipInactive(error(409, exact)));
        assertFalse(SafeServiceError.relationshipInactive(error(
                409, "{\"detail\":{\"code\":\"revision_conflict\"}}")));
        assertFalse(SafeServiceError.relationshipInactive(error(
                409, exact + " ".repeat(4097))));
    }

    private static Response<Object> error(int status, String body) {
        ResponseBody payload = ResponseBody.create(
                body, MediaType.get("application/json"));
        return Response.error(status, payload);
    }
}
