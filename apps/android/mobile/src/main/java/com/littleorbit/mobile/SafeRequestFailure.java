package com.littleorbit.mobile;

import com.littleorbit.data.repository.OrbitServiceException;
import java.util.concurrent.CompletionException;
import java.util.concurrent.ExecutionException;

/** Privacy-safe failure categories for actionable account and pairing messages. */
enum SafeRequestFailure {
    INVALID_CREDENTIALS,
    INVALID_OR_EXPIRED,
    RATE_LIMITED,
    OFFLINE,
    SERVICE_UNAVAILABLE,
    CONFLICT,
    UNKNOWN;

    /** Classifies a sanitized repository failure without inspecting a response body. */
    static SafeRequestFailure classify(Throwable failure) {
        Throwable cause = unwrap(failure);
        if (!(cause instanceof OrbitServiceException service)) return UNKNOWN;
        return switch (service.statusCode()) {
            case -1 -> OFFLINE;
            case 400, 404 -> INVALID_OR_EXPIRED;
            case 401 -> INVALID_CREDENTIALS;
            case 409 -> CONFLICT;
            case 429 -> RATE_LIMITED;
            case 408, 500, 502, 503, 504 -> SERVICE_UNAVAILABLE;
            default -> UNKNOWN;
        };
    }

    /** Returns whether a possibly wrapped failure carries one sanitized HTTP status. */
    static boolean hasStatus(Throwable failure, int statusCode) {
        Throwable cause = unwrap(failure);
        return cause instanceof OrbitServiceException service
                && service.statusCode() == statusCode;
    }

    /** Returns true only for the allowlisted inactive-relationship service code. */
    static boolean relationshipInactive(Throwable failure) {
        Throwable cause = unwrap(failure);
        return cause instanceof OrbitServiceException service
                && service.hasSafeCode("relationship_inactive");
    }

    private static Throwable unwrap(Throwable failure) {
        Throwable current = failure;
        while ((current instanceof CompletionException || current instanceof ExecutionException)
                && current.getCause() != null) {
            current = current.getCause();
        }
        return current;
    }
}
