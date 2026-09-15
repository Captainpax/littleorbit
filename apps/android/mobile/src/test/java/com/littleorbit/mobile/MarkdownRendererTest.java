package com.littleorbit.mobile;

import static org.junit.Assert.assertEquals;
import static org.junit.Assert.assertTrue;

import java.util.Set;
import org.junit.Test;

/** Note-scoped inline-image authorization checks that require no Android runtime. */
public final class MarkdownRendererTest {
    private static final String ALLOWED = "123e4567-e89b-12d3-a456-426614174000";
    private static final String OTHER = "123e4567-e89b-12d3-a456-426614174001";

    @Test
    public void availableImageBecomesAClickableInlinePreview() {
        String source = "Before ![memory](attachment://" + ALLOWED + ") after";
        String prepared = MarkdownRenderer.clickableAvailableImages(source, Set.of(ALLOWED));
        assertTrue(prepared.contains("[![memory](attachment://" + ALLOWED + ")]"));
        assertTrue(prepared.endsWith("(attachment://" + ALLOWED + ") after"));
    }

    @Test
    public void imageOutsideCurrentNoteAllowlistIsNeutralizedUntilAuthorized() {
        String source = "![private](attachment://" + OTHER + ")";
        assertEquals("private", MarkdownRenderer.clickableAvailableImages(source, Set.of(ALLOWED)));
    }

    @Test
    public void neutralizedAltCannotCreateAnotherMarkdownLink() {
        String source = "![tap !(bad)](attachment://" + OTHER + ")";
        assertEquals(
                "tap bad",
                MarkdownRenderer.clickableAvailableImages(source, Set.of()));
    }
}
