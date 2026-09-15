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

    @Test
    void insertionBeforeEmojiSelectionMovesBothUtf16Endpoints() {
        TextPatch patch = TextPatch.between("🌙 notes", "Shared 🌙 notes");

        assertEquals(10, patch.mapOffset(3));
        assertEquals(15, patch.mapOffset(8));
    }

    @Test
    void replacementInsideSelectionKeepsTheSelectionOrdered() {
        TextPatch patch = TextPatch.between("one shared memory", "one new memory");
        int mappedStart = patch.mapOffset(4);
        int mappedEnd = patch.mapOffset(10);

        assertEquals(4, mappedStart);
        assertEquals(7, mappedEnd);
    }

    @Test
    void changeAfterSelectionLeavesBothEndpointsUnchanged() {
        TextPatch patch = TextPatch.between("title and body", "title and longer body");

        assertEquals(0, patch.mapOffset(0));
        assertEquals(5, patch.mapOffset(5));
    }
}
