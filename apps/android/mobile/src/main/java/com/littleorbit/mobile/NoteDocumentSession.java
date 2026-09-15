package com.littleorbit.mobile;

import android.content.Intent;
import android.os.Bundle;
import com.littleorbit.data.remote.NoteApiModels;
import com.littleorbit.data.remote.NoteSocketClient;
import com.littleorbit.data.repository.NoteDraftStore;
import com.littleorbit.data.repository.OrbitRepository;
import com.littleorbit.mobile.databinding.ActivityNotesBinding;
import java.util.List;
import java.util.UUID;

/** Owns one open document's encrypted draft, live editor, and lifecycle transitions. */
final class NoteDocumentSession implements NoteEditorEvents.Host {
    private final NotesActivity activity;
    private final OrbitRepository orbit;
    private final NoteDraftStore drafts;
    private final NoteSocketClient sockets;
    private final ActivityNotesBinding binding;
    private final NoteEditorView screen;
    private final SpaceLibraryViews library;
    private final NoteWorkspaceController workspace;
    private final Runnable reloadDirectory;
    private final Runnable reloadArchived;
    private final NoteEditorObservers observers;
    private NoteAttachmentController attachments;
    private NoteApiModels.Note current;
    private NoteDraftStore.Workspace pendingRestore;
    private String serverBody = "";
    private String createOperationId;
    private int localBaseRevision;
    private int localMetadataRevision;
    private boolean restoringExisting;
    private boolean returnAfterSave;
    private boolean foreground;
    private boolean resumeRequiresReload;
    private long editorGeneration;
    private NoteSocketClient.EditorConnection editor = NoteSocketClient.EditorConnection.closed();
    private final Runnable bodySave = this::sync;
    private final Runnable titleSave = this::rename;
    private final Runnable workspaceSave = this::persistWorkspace;

    NoteDocumentSession(
            NotesActivity activity,
            OrbitRepository orbit,
            NoteDraftStore drafts,
            NoteSocketClient sockets,
            ActivityNotesBinding binding,
            NoteEditorView screen,
            SpaceLibraryViews library,
            NoteWorkspaceController workspace,
            Runnable reloadDirectory,
            Runnable reloadArchived) {
        this.activity = activity;
        this.orbit = orbit;
        this.drafts = drafts;
        this.sockets = sockets;
        this.binding = binding;
        this.screen = screen;
        this.library = library;
        this.workspace = workspace;
        this.reloadDirectory = reloadDirectory;
        this.reloadArchived = reloadArchived;
        observers = new NoteEditorObservers(
                binding.bodyInput, binding.titleInput, screen::isRendering);
    }

    void attach(NoteAttachmentController controller) {
        attachments = controller;
    }

    NoteApiModels.Note current() { return current; }

    boolean hasPendingRestore() { return pendingRestore != null; }

    void bindEditors() {
        observers.bind(() -> {
            observers.schedule(workspaceSave, 300);
            if (current == null || restoringExisting) return;
            drafts.save(current.id, body(), localBaseRevision);
            observers.schedule(bodySave, 750);
        }, () -> {
            observers.schedule(workspaceSave, 300);
            if (current == null || restoringExisting) return;
            observers.schedule(titleSave, 750);
        });
    }

    void select(NoteApiModels.Note note) {
        closeEditor();
        workspace.begin();
        restoringExisting = false;
        pendingRestore = null;
        createOperationId = null;
        current = note;
        serverBody = note.body;
        localMetadataRevision = note.metadataRevision;
        NoteDraftStore.Draft draft = drafts.read(note.id).orElse(null);
        localBaseRevision = draft == null ? note.revision : draft.baseRevision();
        String initialBody = draft == null ? note.body : draft.body();
        screen.renderInitial(note.title, initialBody, initialBody.length(), initialBody.length());
        boolean conflict = draft != null && draft.baseRevision() != note.revision;
        screen.showConflict(conflict ? note.body : null);
        screen.hideRecovery();
        binding.statusText.setText(conflict ? R.string.note_reconcile : R.string.note_ready);
        binding.attachButton.setEnabled(true);
        attachments.reset(note);
        editor = openEditor(note);
        if (draft != null && !conflict) {
            editor.update(draft.body());
            binding.statusText.setText(R.string.syncing_note);
        }
        screen.showDocument(true);
        persistWorkspace();
    }

    void restoreWorkspace(NoteDraftStore.Workspace saved) {
        workspace.consumeRestore();
        createOperationId = saved.createOperationId();
        localBaseRevision = saved.baseRevision();
        localMetadataRevision = saved.metadataRevision();
        serverBody = saved.serverBody();
        screen.renderInitial(
                saved.title(), saved.body(), saved.selectionStart(), saved.selectionEnd());
        screen.showConflict(null);
        attachments.clear();
        if (saved.noteId() == null) restoreNew(saved);
        else restoreExisting(saved);
        screen.showDocument(saved.preview());
    }

    private void restoreNew(NoteDraftStore.Workspace saved) {
        current = null;
        restoringExisting = false;
        binding.attachButton.setEnabled(false);
        binding.statusText.setText(R.string.note_new_hint);
    }

    private void restoreExisting(NoteDraftStore.Workspace saved) {
        current = NoteWorkspaceSnapshots.storedNote(saved);
        pendingRestore = saved;
        restoringExisting = true;
        binding.attachButton.setEnabled(false);
        binding.statusText.setText(R.string.space_restoring_document);
        screen.showRecovery(
                R.string.space_restoring_document,
                R.string.space_retry_document,
                reloadDirectory);
    }

    void reconcileRestore(List<NoteApiModels.Note> notes) {
        NoteDraftStore.Workspace saved = pendingRestore;
        NoteApiModels.Note remote = notes.stream()
                .filter(note -> saved.noteId().equals(note.id)).findFirst().orElse(null);
        if (remote == null) {
            screen.showRecovery(
                    R.string.space_document_unavailable,
                    R.string.space_return_to_library,
                    this::preserveDraftAndReturn);
            return;
        }
        reconcileBody(saved, remote);
        reconcileTitle(saved, remote);
        attachments.reset(remote);
        persistWorkspace();
    }

    private void reconcileBody(
            NoteDraftStore.Workspace saved, NoteApiModels.Note remote) {
        String local = body();
        boolean localChanged = !local.equals(saved.serverBody());
        boolean remoteChanged = saved.baseRevision() != remote.revision;
        current = remote;
        serverBody = remote.body;
        restoringExisting = false;
        pendingRestore = null;
        binding.attachButton.setEnabled(true);
        screen.hideRecovery();
        closeEditor();
        editor = openEditor(remote);
        if (!localChanged) {
            screen.patchBody(remote.body);
            drafts.clear(remote.id);
            localBaseRevision = remote.revision;
        } else if (remoteChanged) {
            screen.showConflict(remote.body);
            binding.statusText.setText(R.string.note_reconcile);
        } else {
            editor.update(local);
            binding.statusText.setText(R.string.syncing_note);
        }
    }

    private void reconcileTitle(
            NoteDraftStore.Workspace saved, NoteApiModels.Note remote) {
        String localTitle = binding.titleInput.getText().toString();
        if (localTitle.equals(saved.serverTitle())) {
            screen.setTitle(remote.title);
            localMetadataRevision = remote.metadataRevision;
        } else if (saved.metadataRevision() == remote.metadataRevision) {
            rename();
        } else {
            binding.statusText.setText(R.string.remote_change_conflict);
        }
    }

    void showLoadFailure() {
        screen.showLoadFailure(restoringExisting, reloadDirectory);
    }

    void relationshipInactive() {
        closeEditor();
        attachments.clear();
        workspace.finish();
        library.setNotes(List.of());
        current = null; pendingRestore = null; createOperationId = null;
        restoringExisting = false; returnAfterSave = false;
        serverBody = ""; localBaseRevision = 0; localMetadataRevision = 0;
        screen.showInactiveRelationship(
                () -> activity.startActivity(new Intent(activity, PairingActivity.class)));
    }

    void newNote() {
        closeEditor();
        workspace.begin();
        current = null;
        pendingRestore = null;
        restoringExisting = false;
        serverBody = "";
        localBaseRevision = 0;
        localMetadataRevision = 0;
        createOperationId = UUID.randomUUID().toString();
        screen.renderInitial("", "", 0, 0);
        screen.showConflict(null);
        screen.hideRecovery();
        attachments.clear();
        binding.attachButton.setEnabled(false);
        binding.statusText.setText(R.string.note_new_hint);
        screen.showDocument(false);
        binding.titleInput.requestFocus();
        persistWorkspace();
    }

    void sync() {
        if (screen.isRendering() || restoringExisting) return;
        if (current == null) {
            if (!title().isEmpty()) create();
            return;
        }
        if (body().equals(serverBody)) {
            binding.statusText.setText(R.string.note_synced);
            finishReturn();
            return;
        }
        drafts.save(current.id, body(), localBaseRevision);
        editor.update(body());
        binding.statusText.setText(R.string.syncing_note);
    }

    private void create() {
        if (title().isEmpty()) {
            binding.statusText.setText(R.string.complete_required_fields);
            return;
        }
        if (createOperationId == null) createOperationId = UUID.randomUUID().toString();
        NoteApiModels.CreateRequest request =
                new NoteApiModels.CreateRequest(createOperationId, title(), body());
        AsyncUi.observe(activity, orbit.createNote(request), binding.statusText, note -> {
            drafts.clear(note.id);
            library.upsert(note);
            boolean returning = returnAfterSave;
            select(note);
            returnAfterSave = returning;
            finishReturn();
        });
    }

    void rename() {
        if (current == null || restoringExisting) return;
        if (title().isEmpty() || title().equals(current.title)) {
            finishReturn();
            return;
        }
        NoteApiModels.TitleRequest request = new NoteApiModels.TitleRequest(
                UUID.randomUUID().toString(), localMetadataRevision, title());
        orbit.renameNote(current.id, request).thenAccept(note -> activity.runOnUiThread(() -> {
            current = note;
            localMetadataRevision = note.metadataRevision;
            library.upsert(note);
            persistWorkspace();
            finishReturn();
        })).exceptionally(failure -> {
            activity.runOnUiThread(() -> showRenameFailure());
            return null;
        });
    }

    private void showRenameFailure() {
        screen.showRenameFailure(reloadDirectory);
    }

    void confirmArchive() {
        if (current == null) return;
        new com.google.android.material.dialog.MaterialAlertDialogBuilder(activity)
                .setTitle(R.string.archive_note)
                .setMessage(R.string.archive_note_explanation)
                .setNegativeButton(android.R.string.cancel, null)
                .setPositiveButton(R.string.archive_action, (dialog, which) -> archive())
                .show();
    }

    private void archive() {
        NoteApiModels.ArchiveRequest request = new NoteApiModels.ArchiveRequest(
                UUID.randomUUID().toString(), current.metadataRevision);
        AsyncUi.observe(activity, orbit.archiveNote(current.id, request), binding.statusText, note -> {
            drafts.clear(note.id);
            library.remove(note.id);
            leaveWorkspace();
            reloadArchived.run();
        });
    }

    void returnToLibrary() {
        if (current == null) {
            returnFromNewNote();
            return;
        }
        returnAfterSave = true;
        rename();
        sync();
        finishReturn();
    }

    private void returnFromNewNote() {
        if (title().isEmpty() && body().isBlank()) {
            leaveWorkspace();
        } else if (!title().isEmpty()) {
            returnAfterSave = true;
            create();
        } else {
            showUntitledDialog();
        }
    }

    private void showUntitledDialog() {
        new com.google.android.material.dialog.MaterialAlertDialogBuilder(activity)
                .setTitle(R.string.space_untitled_draft)
                .setMessage(R.string.space_untitled_draft_message)
                .setNegativeButton(R.string.keep_editing, null)
                .setPositiveButton(R.string.discard_draft, (dialog, which) -> leaveWorkspace())
                .show();
    }

    private void finishReturn() {
        if (!returnAfterSave || current == null) return;
        if (!body().equals(serverBody) || !title().equals(current.title)) return;
        returnAfterSave = false;
        leaveWorkspace();
    }

    private void leaveWorkspace() {
        closeEditor();
        attachments.clear();
        screen.clearPreview();
        screen.showLibrary();
        workspace.finish();
        current = null;
        pendingRestore = null;
        restoringExisting = false;
        serverBody = "";
    }

    private void preserveDraftAndReturn() {
        if (current != null) drafts.save(current.id, body(), localBaseRevision);
        leaveWorkspace();
    }

    void abandon() {
        workspace.finish();
        closeEditor();
        attachments.clear();
        current = null;
        pendingRestore = null;
        restoringExisting = false;
    }

    void useServerVersion() {
        if (current == null) return;
        editor.acceptServer();
        screen.patchBody(serverBody);
        localBaseRevision = current.revision;
        drafts.clear(current.id);
        screen.showConflict(null);
        binding.statusText.setText(R.string.note_ready);
        persistWorkspace();
    }

    void keepMyVersion() {
        if (current == null) return;
        screen.showConflict(null);
        localBaseRevision = current.revision;
        editor.keepLocal(body());
        binding.statusText.setText(R.string.syncing_note);
        persistWorkspace();
    }

    private NoteSocketClient.EditorConnection openEditor(NoteApiModels.Note note) {
        if (!foreground) {
            resumeRequiresReload = true;
            return NoteSocketClient.EditorConnection.closed();
        }
        long generation = ++editorGeneration;
        return sockets.openEditor(
                note.id, note.body, note.revision,
                new NoteEditorEvents(activity, note.id, generation, this));
    }

    private void closeEditor() {
        editorGeneration++;
        editor.close();
        editor = NoteSocketClient.EditorConnection.closed();
    }

    private void persistWorkspace() {
        if (!screen.isEditorVisible()) return;
        workspace.persist(snapshot());
    }

    private NoteDraftStore.Workspace snapshot() {
        int start = Math.max(binding.bodyInput.getSelectionStart(), 0);
        int end = Math.max(binding.bodyInput.getSelectionEnd(), start);
        return NoteWorkspaceSnapshots.capture(
                current, binding.titleInput.getText().toString(), body(), serverBody,
                localBaseRevision, localMetadataRevision, createOperationId,
                start, end, screen.isPreviewing());
    }

    void pause() {
        foreground = false;
        observers.cancel(bodySave, titleSave, workspaceSave);
        if (current != null && !body().equals(serverBody)) {
            drafts.save(current.id, body(), localBaseRevision);
        }
        if (screen.isEditorVisible()) workspace.persistNow(snapshot());
        resumeRequiresReload = current != null && !restoringExisting;
        closeEditor();
    }

    void resume() {
        foreground = true;
        if (!resumeRequiresReload) return;
        resumeRequiresReload = false;
        reloadCurrent();
    }

    void destroy() {
        foreground = false;
        resumeRequiresReload = false;
        closeEditor();
        screen.clearPreview();
        observers.clear();
    }

    void saveState(Bundle state) {
        if (screen.isEditorVisible()) workspace.persistNow(snapshot());
        workspace.saveReference(state);
    }

    private String title() { return binding.titleInput.getText().toString().trim(); }

    private String body() { return binding.bodyInput.getText().toString(); }

    private void reloadCurrent() {
        if (current == null) return;
        pendingRestore = snapshot();
        restoringExisting = true;
        closeEditor();
        attachments.clear();
        binding.attachButton.setEnabled(false);
        reloadDirectory.run();
    }

    @Override public boolean isActive(String noteId, long generation) {
        return current != null && noteId.equals(current.id) && generation == editorGeneration;
    }

    @Override public void applyRemote(String body, int revision) {
        String local = body();
        String priorServer = serverBody;
        serverBody = body;
        current = NoteWorkspaceSnapshots.withBody(current, body, revision);
        if (local.equals(priorServer) || local.equals(body)) {
            screen.patchBody(body);
            localBaseRevision = revision;
            drafts.clear(current.id);
            screen.hideRecovery();
            binding.statusText.setText(R.string.note_synced);
        } else {
            screen.showConflict(body);
            binding.statusText.setText(R.string.note_reconcile);
        }
        persistWorkspace();
    }

    @Override public void applySaved(String body, int revision) {
        serverBody = body;
        current = NoteWorkspaceSnapshots.withBody(current, body, revision);
        localBaseRevision = revision;
        String local = body();
        if (local.equals(body)) {
            drafts.clear(current.id);
            screen.showConflict(null);
            screen.hideRecovery();
            binding.statusText.setText(R.string.note_synced);
            library.upsert(current);
            finishReturn();
        } else {
            drafts.save(current.id, local, revision);
            binding.statusText.setText(R.string.syncing_note);
        }
        persistWorkspace();
    }

    @Override public void applyConflict(String body, int revision) {
        serverBody = body;
        current = NoteWorkspaceSnapshots.withBody(current, body, revision);
        screen.showConflict(body);
        binding.statusText.setText(R.string.note_reconcile);
        persistWorkspace();
    }

    @Override public void applyFailure() {
        binding.statusText.setText(R.string.note_draft_preserved);
        screen.showRecovery(
                R.string.note_draft_preserved,
                R.string.space_retry_document,
                this::reloadCurrent);
    }

    @Override public void applyTerminalFailure() { reloadCurrent(); }

    @Override public void applyPresence(int editors) {
        int label = editors > 1
                ? R.string.note_presence_together : R.string.note_presence_solo;
        binding.presenceText.setText(label);
        binding.libraryPresenceText.setText(label);
    }
}
