package com.littleorbit.data.remote;

import static org.junit.Assert.assertEquals;
import static org.junit.Assert.assertFalse;
import static org.junit.Assert.assertTrue;

import java.util.List;
import org.junit.Test;

/** Regression tests for Unicode-safe note operations produced by the Android editor. */
public final class NoteSocketClientTest {
    @Test
    public void editPlanUsesCodePointOffsetsAroundEmoji() {
        List<NoteSocketClient.Operation> operations =
                NoteSocketClient.editPlan("Hi 🪐 there", "Hi 🪐 friend");

        assertEquals(2, operations.size());
        assertEquals("delete", operations.get(0).kind());
        assertEquals(5, operations.get(0).position());
        assertEquals(5, operations.get(0).length());
        assertEquals("insert", operations.get(1).kind());
        assertEquals(5, operations.get(1).position());
        assertEquals("friend", operations.get(1).text());
    }

    @Test
    public void editPlanDoesNothingForIdenticalContent() {
        assertEquals(List.of(), NoteSocketClient.editPlan("same", "same"));
    }

    @Test
    public void authorizationAndCompatibilityClosesRequireHttpRecheck() {
        assertTrue(NoteSocketClient.terminalCloseCode(4401));
        assertTrue(NoteSocketClient.terminalCloseCode(4403));
        assertTrue(NoteSocketClient.terminalCloseCode(4426));
        assertFalse(NoteSocketClient.terminalCloseCode(1001));
    }
}
