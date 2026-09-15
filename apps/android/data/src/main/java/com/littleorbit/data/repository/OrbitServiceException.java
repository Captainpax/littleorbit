package com.littleorbit.data.repository;

import java.io.IOException;

/** Sanitized service failure that never includes response bodies or credentials. */
public final class OrbitServiceException extends RuntimeException {
    private final int statusCode;
    private final String safeCode;

    /** Creates an HTTP-status failure. */
    public OrbitServiceException(int statusCode) {
        super("Little Orbit request failed with status " + statusCode);
        this.statusCode = statusCode;
        this.safeCode = null;
    }

    /** Creates a transport failure without secret-bearing request data. */
    public OrbitServiceException(IOException cause) {
        super("Little Orbit could not reach the server", cause);
        this.statusCode = -1;
        this.safeCode = null;
    }

    /** Creates a sanitized local failure without content or paths. */
    public OrbitServiceException(int statusCode, String reason) {
        super(reason);
        this.statusCode = statusCode;
        this.safeCode = reason;
    }

    /** Creates a sanitized local failure with its transport cause. */
    public OrbitServiceException(int statusCode, String reason, Throwable cause) {
        super(reason, cause);
        this.statusCode = statusCode;
        this.safeCode = reason;
    }

    /** Returns the HTTP status or -1 for transport and local failures. */
    public int statusCode() {
        return statusCode;
    }

    /** Returns whether this failure carries one allowlisted privacy-safe service code. */
    public boolean hasSafeCode(String wanted) {
        return safeCode != null && safeCode.equals(wanted);
    }
}
