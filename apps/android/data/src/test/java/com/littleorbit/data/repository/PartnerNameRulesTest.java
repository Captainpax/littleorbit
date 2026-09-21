package com.littleorbit.data.repository;

import static org.junit.Assert.assertEquals;
import static org.junit.Assert.assertThrows;

import org.junit.Test;

/** Mirrors server-side shared-name validation for fast accessible form feedback. */
public final class PartnerNameRulesTest {
    @Test
    public void friendlyUnicodeAndEmojiAreAccepted() {
        assertEquals("Amélie 🦉", PartnerNameRules.normalize("  Amélie 🦉  "));
        assertEquals("Space 👩‍🚀", PartnerNameRules.normalize("Space 👩‍🚀"));
    }

    @Test
    public void contactAndControlDataAreRejected() {
        for (String value : new String[] {
                "", "x".repeat(41), "two\nlines", "person@example.com",
                "+1 (555) 123-4567", "https://example.com", "www.example.org"
        }) {
            assertThrows(IllegalArgumentException.class, () -> PartnerNameRules.normalize(value));
        }
    }
}
