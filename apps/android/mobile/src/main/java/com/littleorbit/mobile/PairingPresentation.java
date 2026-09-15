package com.littleorbit.mobile;

import java.time.Duration;
import java.time.Instant;
import java.util.Locale;

/** Pure pair-code normalization and expiry presentation. */
final class PairingPresentation {
    private PairingPresentation() {}

    /** Removes pasted separators and normalizes the eight-character code. */
    static String normalizeCode(String value) {
        if (value == null) return "";
        return value.replaceAll("[^A-Za-z0-9]", "").toUpperCase(Locale.ROOT);
    }

    /** Returns non-negative seconds until the server expiry instant. */
    static long secondsRemaining(Instant expiresAt, Instant now) {
        long millis = Duration.between(now, expiresAt).toMillis();
        return Math.max(0, (millis + 999) / 1_000);
    }

    /** Formats a short accessible countdown as m:ss. */
    static String clock(long totalSeconds) {
        long safe = Math.max(0, totalSeconds);
        return String.format(Locale.ROOT, "%d:%02d", safe / 60, safe % 60);
    }
}
