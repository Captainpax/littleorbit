package com.littleorbit.domain;

import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertTrue;

import org.junit.jupiter.api.Test;

/** Privacy regression checks for Markdown rendering. */
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
        assertTrue(preview.startsWith("&lt;script>"));
        assertTrue(preview.contains("\n<b>code</b>\n"));
        assertTrue(MarkdownPrivacy.containsRawHtml("<script>bad()</script>"));
    }

    @Test
    void gfmFeaturesAndSafeAutolinksSurvivePrivacyTransform() {
        String markdown = "| A | B |\n| - | - |\n| 1 | 2 |\n"
                + "- [ ] task\n~~later~~\n<https://example.test>\n```java\n<b>code</b>\n```";
        assertEquals(markdown, MarkdownPrivacy.forPreview(markdown));
    }

    @Test
    void inlineAndTildeFencedCodeStayLiteralWhileHtmlOutsideIsNeutralized() {
        String markdown = "`<b>inline</b>`\n~~~html\n<img src=x>\n~~~\n<img src=x>";
        String preview = MarkdownPrivacy.forPreview(markdown);
        assertTrue(preview.contains("`<b>inline</b>`"));
        assertTrue(preview.contains("~~~html\n<img src=x>\n~~~"));
        assertTrue(preview.endsWith("&lt;img src=x>"));
        assertTrue(MarkdownPrivacy.forPreview("` unmatched <img src=x>")
                .endsWith("&lt;img src=x>"));
        assertEquals("    <b>indented code</b>",
                MarkdownPrivacy.forPreview("    <b>indented code</b>"));
    }

    @Test
    void privateAttachmentImagesRemainEligibleForAuthorizedRenderer() {
        String attachment = "![memory](attachment://123e4567-e89b-12d3-a456-426614174000)";
        assertEquals(attachment, MarkdownPrivacy.forPreview(attachment));
    }
}
