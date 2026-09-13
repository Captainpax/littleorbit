package com.littleorbit.data.repository;

import java.io.IOException;

/** Sanitized service failure that never includes response bodies or credentials. */
public final class OrbitServiceException extends RuntimeException {
    private final int statusCode;

    /** Creates an HTTP-status failure. */
    public OrbitServiceException(int statusCode) {
        super("Little Orbit request failed with status " + statusCode);
        this.statusCode = statusCode;
    }

    /** Creates a transport failure without secret-bearing request data. */
    public OrbitServiceException(IOException cause) {
        super("Little Orbit could not reach the server", cause);
        this.statusCode = -1;
    }

    /** Creates a sanitized local failure without content or paths. */
    public OrbitServiceException(int statusCode, String reason) {
        super(reason);
        this.statusCode = statusCode;
    }

    /** Creates a sanitized local failure with its transport cause. */
    public OrbitServiceException(int statusCode, String reason, Throwable cause) {
        super(reason, cause);
        this.statusCode = statusCode;
    }

    /** Returns the HTTP status or -1 for transport and local failures. */
    public int statusCode() {
        return statusCode;
    }
}
