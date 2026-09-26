package com.littleorbit.mobile;

import static org.junit.Assert.assertEquals;

import java.util.Locale;
import org.junit.Test;

/** Ensures model-generated quiz copy renders with predictable inline spacing. */
public final class QuizTypographyTest {
    @Test
    public void collapsesUnicodeAndMultilineGaps() {
        assertEquals("A calmer question today",
                QuizTypography.inline("  A\u00a0calmer\n question\u200btoday  "));
    }

    @Test
    public void categoryCaseDoesNotDependOnPhoneLocale() {
        Locale previous = Locale.getDefault();
        try {
            Locale.setDefault(Locale.forLanguageTag("tr-TR"));
            assertEquals("MUTUAL · DAILY LIFE",
                    QuizTypography.category("daily_life", true));
        } finally {
            Locale.setDefault(previous);
        }
    }

    @Test
    public void nullGeneratedCopyIsSafe() {
        assertEquals("", QuizTypography.inline(null));
    }
}
