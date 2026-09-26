package com.littleorbit.domain;

import java.util.Locale;
import java.util.Objects;
import java.util.regex.Pattern;

/** Validated unambiguous eight-character code used only during pairing. */
public record PairCode(String value) {
    private static final Pattern FORMAT = Pattern.compile("^[ABCDEFGHJKLMNPQRSTUVWXYZ23456789]{8}$");

    /** Normalizes and validates a user-entered pairing code. */
    public PairCode {
        Objects.requireNonNull(value, "value");
        value = value.trim().toUpperCase(Locale.ROOT);
        if (!FORMAT.matcher(value).matches()) {
            throw new IllegalArgumentException("pair code is not eight unambiguous characters");
        }
    }
}
