package com.littleorbit.domain;

import static org.junit.jupiter.api.Assertions.assertEquals;

import org.junit.jupiter.api.Test;

/** Unicode and selection regression checks for live note updates. */
final class TextPatchTest {
    @Test
    void insertionAfterEmojiKeepsCursorAtTheLogicalEnd() {
        TextPatch patch = TextPatch.between("A😘B", "A😘 bright B");
        assertEquals(3, patch.start());
        assertEquals(3, patch.end());
        assertEquals(12, patch.mapOffset(4));
    }

    @Test
    void replacementBeforeSelectionMovesItByTheReplacementDelta() {
        TextPatch patch = TextPatch.between("hello world", "hi world");
        assertEquals(8, patch.mapOffset(11));
    }
}
