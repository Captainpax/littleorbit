package com.littleorbit.mobile;

import java.util.Locale;
import java.util.regex.Pattern;

/** Normalizes generated inline quiz copy without changing saved free-text answers. */
final class QuizTypography {
    private static final Pattern INLINE_GAPS = Pattern.compile("[\\s\\p{Zs}\\u200B\\uFEFF]+");

    private QuizTypography() {}

    /** Collapses accidental Unicode spacing in model-generated prompts and options. */
    static String inline(String value) {
        if (value == null) return "";
        return INLINE_GAPS.matcher(value.strip()).replaceAll(" ");
    }

    /** Produces a stable, locale-independent category label. */
    static String category(String value, boolean intimacy) {
        String label = inline(value).replace('_', ' ').toUpperCase(Locale.ROOT);
        return intimacy ? "MUTUAL · " + label : label;
    }
}
