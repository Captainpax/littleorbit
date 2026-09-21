package com.littleorbit.data.repository;

import java.text.Normalizer;
import java.util.Locale;
import java.util.regex.Pattern;

/** Client-side mirror of the server's friendly, non-contact relationship-name rules. */
public final class PartnerNameRules {
    private static final Pattern EMAIL = Pattern.compile(
            "\\b[^\\s@]+@[^\\s@]+\\.[^\\s@]+\\b", Pattern.CASE_INSENSITIVE);
    private static final Pattern URL = Pattern.compile(
            "(?:https?://|www\\.)|(?:\\b[a-z0-9-]+\\.)+(?:com|net|org|io|app|dev|co|me)\\b",
            Pattern.CASE_INSENSITIVE);
    private static final Pattern PHONE = Pattern.compile("^[+()\\d.\\-\\s]+$");

    private PartnerNameRules() {}

    /** Returns normalized input or throws a content-free validation error. */
    public static String normalize(String value) {
        String normalized = Normalizer.normalize(value == null ? "" : value, Normalizer.Form.NFKC)
                .strip();
        int length = normalized.codePointCount(0, normalized.length());
        if (length < 1 || length > 40) {
            throw new IllegalArgumentException("Name must be between 1 and 40 characters");
        }
        if (normalized.codePoints().anyMatch(PartnerNameRules::forbidden)) {
            throw new IllegalArgumentException("Name cannot contain controls or line breaks");
        }
        if (looksLikeContact(normalized)) {
            throw new IllegalArgumentException(
                    "Name cannot be an email address, phone number, or URL");
        }
        return normalized;
    }

    private static boolean forbidden(int value) {
        int type = Character.getType(value);
        return type == Character.CONTROL
                || type == Character.SURROGATE
                || type == Character.LINE_SEPARATOR
                || type == Character.PARAGRAPH_SEPARATOR
                || (type == Character.FORMAT && value != 0x200D);
    }

    private static boolean looksLikeContact(String value) {
        long digits = value.codePoints().filter(Character::isDigit).count();
        String lowered = value.toLowerCase(Locale.ROOT);
        return EMAIL.matcher(value).find()
                || URL.matcher(lowered).find()
                || (digits >= 7 && PHONE.matcher(value).matches());
    }
}
