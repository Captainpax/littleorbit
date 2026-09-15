package com.littleorbit.mobile;

import static org.junit.Assert.assertEquals;
import static org.junit.Assert.assertNull;

import com.littleorbit.data.remote.NoteApiModels;
import com.littleorbit.data.repository.NoteDraftStore;
import org.junit.Test;

/** Process-restoration snapshot mapping checks with Unicode selection offsets. */
public final class NoteWorkspaceSnapshotsTest {
    @Test
    public void newDraftKeepsOnlyEncryptedWorkspaceValues() {
        NoteDraftStore.Workspace saved = NoteWorkspaceSnapshots.capture(
                null, "Our plan", "Hi 😘", "", 0, 0, "stable-create", 3, 5, false);
        assertNull(saved.noteId());
        assertEquals("stable-create", saved.createOperationId());
        assertEquals(3, saved.selectionStart());
        assertEquals(5, saved.selectionEnd());
    }

    @Test
    public void storedServerSnapshotRoundTripsWithoutUsingLocalBody() {
        NoteApiModels.Note note = new NoteApiModels.Note(
                "123e4567-e89b-12d3-a456-426614174010", "Server", "old", 4, 2,
                "2026-09-14T00:00:00Z", null, null);
        NoteDraftStore.Workspace saved = NoteWorkspaceSnapshots.capture(
                note, "Local title", "local", "old", 4, 2, null, 5, 5, true);
        NoteApiModels.Note restored = NoteWorkspaceSnapshots.storedNote(saved);
        assertEquals("Server", restored.title);
        assertEquals("old", restored.body);
        assertEquals(4, restored.revision);
    }
}
