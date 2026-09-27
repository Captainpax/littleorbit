package com.littleorbit.mobile;

import com.littleorbit.data.remote.NoteApiModels;
import com.littleorbit.data.repository.NoteDraftStore;
import java.util.List;

/** Restores one encrypted workspace without inventing a replacement document identity. */
final class NoteWorkspaceRestoreCoordinator {
    private final NoteDocumentSession session;

    NoteWorkspaceRestoreCoordinator(NoteDocumentSession session) {
        this.session = session;
    }

    void restore(NoteDraftStore.Workspace saved) {
        session.workspace.consumeRestore();
        session.creation.restore(saved.createOperationId());
        session.localBaseRevision = saved.baseRevision();
        session.localMetadataRevision = saved.metadataRevision();
        session.serverBody = saved.serverBody();
        session.screen.renderInitial(
                saved.title(), saved.body(), saved.selectionStart(), saved.selectionEnd());
        session.screen.showConflict(null);
        session.attachments.clear();
        if (saved.noteId() == null) restoreNew();
        else restoreExisting(saved);
        session.screen.showDocument(saved.preview());
    }

    void reconcile(List<NoteApiModels.Note> notes) {
        NoteDraftStore.Workspace saved = session.pendingRestore;
        NoteApiModels.Note remote = notes.stream()
                .filter(note -> saved.noteId().equals(note.id)).findFirst().orElse(null);
        if (remote == null) {
            session.screen.showRecovery(
                    R.string.space_document_unavailable,
                    R.string.space_return_to_library,
                    session::preserveDraftAndReturn);
            return;
        }
        reconcileBody(saved, remote);
        reconcileTitle(saved, remote);
        session.attachments.reset(remote);
        session.persistWorkspace();
    }

    private void restoreNew() {
        session.current = null;
        session.restoringExisting = false;
        session.binding.attachButton.setEnabled(false);
        session.binding.statusText.setText(R.string.note_new_hint);
    }

    private void restoreExisting(NoteDraftStore.Workspace saved) {
        session.current = NoteWorkspaceSnapshots.storedNote(saved);
        session.pendingRestore = saved;
        session.restoringExisting = true;
        session.binding.attachButton.setEnabled(false);
        session.binding.statusText.setText(R.string.space_restoring_document);
        session.screen.showRecovery(
                R.string.space_restoring_document,
                R.string.space_retry_document,
                session.reloadDirectory);
    }

    private void reconcileBody(
            NoteDraftStore.Workspace saved, NoteApiModels.Note remote) {
        String local = session.body();
        boolean localChanged = !local.equals(saved.serverBody());
        boolean remoteChanged = saved.baseRevision() != remote.revision;
        session.current = remote;
        session.serverBody = remote.body;
        session.restoringExisting = false;
        session.pendingRestore = null;
        session.binding.attachButton.setEnabled(true);
        session.screen.hideRecovery();
        session.closeEditor();
        session.editor = session.openEditor(remote);
        if (!localChanged) {
            session.screen.patchBody(remote.body);
            session.drafts.clear(remote.id);
            session.localBaseRevision = remote.revision;
        } else if (remoteChanged) {
            session.screen.showConflict(remote.body);
            session.needsReview = true;
            session.binding.statusText.setText(R.string.note_needs_review);
        } else {
            session.editor.update(local);
            session.binding.statusText.setText(R.string.syncing_note);
        }
    }

    private void reconcileTitle(
            NoteDraftStore.Workspace saved, NoteApiModels.Note remote) {
        String localTitle = session.binding.titleInput.getText().toString();
        if (localTitle.equals(saved.serverTitle())) {
            session.screen.setTitle(remote.title);
            session.localMetadataRevision = remote.metadataRevision;
        } else if (saved.metadataRevision() == remote.metadataRevision) {
            session.rename();
        } else {
            session.binding.statusText.setText(R.string.remote_change_conflict);
        }
    }
}
