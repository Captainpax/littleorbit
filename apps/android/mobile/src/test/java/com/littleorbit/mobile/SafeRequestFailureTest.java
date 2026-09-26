package com.littleorbit.mobile;

import static org.junit.Assert.assertEquals;

import com.littleorbit.data.repository.OrbitServiceException;
import java.io.IOException;
import java.util.concurrent.CompletionException;
import org.junit.Test;

/** Locks privacy-safe Android error categories to sanitized repository failures. */
public final class SafeRequestFailureTest {
    @Test
    public void classifiesActionableHttpFailures() {
        assertEquals(SafeRequestFailure.INVALID_CREDENTIALS, classify(401));
        assertEquals(SafeRequestFailure.INVALID_OR_EXPIRED, classify(404));
        assertEquals(SafeRequestFailure.CONFLICT, classify(409));
        assertEquals(SafeRequestFailure.RATE_LIMITED, classify(429));
        assertEquals(SafeRequestFailure.SERVICE_UNAVAILABLE, classify(408));
        assertEquals(SafeRequestFailure.SERVICE_UNAVAILABLE, classify(503));
    }

    @Test
    public void unwrapsTransportFailureWithoutReadingResponseContent() {
        Throwable failure = new CompletionException(
                new OrbitServiceException(new IOException("offline")));

        assertEquals(SafeRequestFailure.OFFLINE, SafeRequestFailure.classify(failure));
    }

    @Test
    public void unknownFailureRemainsGeneric() {
        assertEquals(SafeRequestFailure.UNKNOWN,
                SafeRequestFailure.classify(new IllegalStateException("private detail")));
    }

    @Test
    public void requiresExactSafeCodeForRelationshipInvalidation() {
        Throwable inactive = new CompletionException(
                new OrbitServiceException(409, "relationship_inactive"));
        Throwable ordinaryConflict = new CompletionException(new OrbitServiceException(409));

        org.junit.Assert.assertTrue(SafeRequestFailure.relationshipInactive(inactive));
        org.junit.Assert.assertFalse(SafeRequestFailure.relationshipInactive(ordinaryConflict));
        org.junit.Assert.assertTrue(SafeRequestFailure.hasStatus(ordinaryConflict, 409));
    }

    private static SafeRequestFailure classify(int statusCode) {
        return SafeRequestFailure.classify(new OrbitServiceException(statusCode));
    }
}
