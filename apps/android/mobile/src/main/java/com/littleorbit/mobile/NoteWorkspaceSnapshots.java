package com.littleorbit.mobile;

import com.littleorbit.data.remote.NoteApiModels;
import com.littleorbit.data.repository.NoteDraftStore;

/** Pure mapping between encrypted workspace state and note wire snapshots. */
final class NoteWorkspaceSnapshots {
    private NoteWorkspaceSnapshots() {}

    static NoteApiModels.Note storedNote(NoteDraftStore.Workspace saved) {
        return new NoteApiModels.Note(
                saved.noteId(), saved.serverTitle(), saved.serverBody(),
                saved.baseRevision(), saved.metadataRevision(), saved.updatedAt(),
                saved.archivedAt(), saved.purgeAfter());
    }

    static NoteApiModels.Note withBody(
            NoteApiModels.Note current, String body, int revision) {
        return new NoteApiModels.Note(
                current.id, current.title, body, revision, current.metadataRevision,
                current.updatedAt, current.archivedAt, current.purgeAfter);
    }

    static NoteDraftStore.Workspace capture(
            NoteApiModels.Note current,
            String title,
            String body,
            String serverBody,
            int baseRevision,
            int metadataRevision,
            String createOperationId,
            int selectionStart,
            int selectionEnd,
            boolean preview) {
        return new NoteDraftStore.Workspace(
                current == null ? null : current.id,
                current == null ? "" : current.title,
                title,
                serverBody,
                body,
                baseRevision,
                metadataRevision,
                current == null ? null : current.updatedAt,
                current == null ? null : current.archivedAt,
                current == null ? null : current.purgeAfter,
                createOperationId,
                selectionStart,
                selectionEnd,
                preview);
    }
}
