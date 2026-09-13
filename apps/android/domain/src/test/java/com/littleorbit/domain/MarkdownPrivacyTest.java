package com.littleorbit.domain;

import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertTrue;

import org.junit.jupiter.api.Test;

/** Privacynahme regression checks for Markdown rendering. */
final class MarkdownPrivacyTest {
    @Test
    void remoteImagesBecomeTapToOpenLinks() {
        String preview = MarkdownPrivacy.forPreview("![sunset](https://example.test/photo.jpg)");
        assertFalse(preview.startsWith("!"));
        assertTrue(preview.contains("Remote image blocked: sunset"));
    }

    @Test
    void rawHtmlIsEscapedOutsideCodeFences() {
        String preview = MarkdownPrivacy.forPreview("<script>bad()</script>\n```\n<b>code</b>\n```");
        assertTrue(preview.startsWith("&lt;script&gt;"));
        assertTrue(preview.contains("\n<b>code</b>\n"));
    }
}
