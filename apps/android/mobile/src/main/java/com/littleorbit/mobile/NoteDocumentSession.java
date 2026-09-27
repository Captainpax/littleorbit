package com.littleorbit.mobile;

import android.content.Intent;
import android.os.Bundle;
import com.littleorbit.data.remote.NoteApiModels;
import com.littleorbit.data.remote.NoteSocketClient;
import com.littleorbit.data.repository.NoteDraftStore;
import com.littleorbit.data.repository.OrbitRepository;
import com.littleorbit.mobile.databinding.ActivityNotesBinding;
import java.nio.charset.StandardCharsets;
import java.util.List;
import java.util.UUID;

/** Owns one open document's encrypted draft, live editor, and lifecycle transitions. */
final class NoteDocumentSession implements NoteEditorEvents.Host {
    private final NotesActivity activity;
    private final OrbitRepository orbit;
    final NoteDraftStore drafts;
    private final NoteSocketClient sockets;
    final ActivityNotesBinding binding;
    final NoteEditorView screen;
    private final SpaceLibraryViews library;
    final NoteWorkspaceController workspace;
    final Runnable reloadDirectory;
    private final Runnable reloadArchived;
    private final NoteEditorObservers observers;
    private final NoteAutosaveScheduler autosave;
    private final NoteWorkspaceRestoreCoordinator restore;
    private final NoteArchiveCoordinator archive;
    NoteAttachmentController attachments;
    NoteApiModels.Note current;
    NoteDraftStore.Workspace pendingRestore;
    String serverBody = "";
    final NoteCreationCoordinator creation = new NoteCreationCoordinator();
    int localBaseRevision;
    int localMetadataRevision;
    boolean restoringExisting, returnAfterSave, foreground, resumeRequiresReload;
    boolean metadataInFlight, bodyInFlight, savePending, needsReview;
    private long editorGeneration;
    NoteSocketClient.EditorConnection editor = NoteSocketClient.EditorConnection.closed();
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
        autosave = new NoteAutosaveScheduler(this::requestAutosave);
        restore = new NoteWorkspaceRestoreCoordinator(this);
        archive = new NoteArchiveCoordinator(
                activity, orbit, drafts, binding, library, () -> current,
                this::leaveWorkspace, reloadArchived);
    }

    void attach(NoteAttachmentController controller) {
        attachments = controller;
    }

    NoteApiModels.Note current() { return current; }

    boolean hasPendingRestore() { return pendingRestore != null; }

    void bindEditors() {
        observers.bind(() -> {
            observers.schedule(workspaceSave, 300);
            if (restoringExisting || needsReview) return;
            if (current != null) drafts.save(current.id, body(), localBaseRevision);
            binding.statusText.setText(R.string.note_offline_saved);
            autosave.edited();
        }, () -> {
            observers.schedule(workspaceSave, 300);
            if (restoringExisting || needsReview) return;
            binding.statusText.setText(R.string.note_offline_saved);
            autosave.edited();
        });
    }

    void select(NoteApiModels.Note note) {
        closeEditor();
        workspace.begin();
        restoringExisting = false;
        needsReview = false;
        metadataInFlight = false;
        bodyInFlight = false;
        savePending = false;
        pendingRestore = null;
        creation.clear();
        current = note;
        serverBody = note.body;
        localMetadataRevision = note.metadataRevision;
        NoteDraftStore.Draft draft = drafts.read(note.id).orElse(null);
        localBaseRevision = draft == null ? note.revision : draft.baseRevision();
        String initialBody = draft == null ? note.body : draft.body();
        screen.renderInitial(note.title, initialBody, initialBody.length(), initialBody.length());
        boolean conflict = draft != null && draft.baseRevision() != note.revision;
        screen.showConflict(conflict ? note.body : null);
        needsReview = conflict;
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
        restore.restore(saved);
    }

    void reconcileRestore(List<NoteApiModels.Note> notes) {
        restore.reconcile(notes);
    }

    void showLoadFailure() {
        screen.showLoadFailure(restoringExisting, reloadDirectory);
    }

    void relationshipInactive() {
        closeEditor();
        attachments.clear();
        workspace.finish();
        library.setNotes(List.of());
        current = null; pendingRestore = null; creation.clear();
        restoringExisting = false; returnAfterSave = false;
        metadataInFlight = false; bodyInFlight = false; savePending = false; needsReview = false;
        serverBody = ""; localBaseRevision = 0; localMetadataRevision = 0;
        screen.showInactiveRelationship(
                () -> activity.startActivity(new Intent(activity, PairingActivity.class)));
    }

    void newNote() {
        if (screen.isEditorVisible() && current == null) {
            binding.titleInput.requestFocus();
            return;
        }
        closeEditor();
        workspace.begin();
        current = null;
        pendingRestore = null;
        restoringExisting = false;
        needsReview = false;
        serverBody = "";
        localBaseRevision = 0;
        localMetadataRevision = 0;
        creation.begin();
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

    private void requestAutosave() {
        if (screen.isRendering() || restoringExisting || needsReview) return;
        savePending = true;
        drainAutosave();
    }

    private void drainAutosave() {
        if (!savePending || creation.inFlight() || metadataInFlight || bodyInFlight) return;
        savePending = false;
        if (current == null) {
            if (!title().isEmpty()) create();
            return;
        }
        if (!title().isEmpty() && !title().equals(current.title)) {
            startRename();
        } else if (!body().equals(serverBody)) {
            startBodySave();
        } else {
            binding.statusText.setText(R.string.note_saved_now);
            finishReturn();
        }
    }

    private void startBodySave() {
        drafts.save(current.id, body(), localBaseRevision);
        bodyInFlight = true;
        editor.update(body());
        binding.statusText.setText(R.string.note_saving);
    }

    private void create() {
        if (title().isEmpty()) {
            binding.statusText.setText(R.string.complete_required_fields);
            return;
        }
        workspace.persistNow(snapshot());
        binding.statusText.setText(R.string.note_saving);
        creation.submit(
                activity, orbit, binding.statusText, title(), body(), () -> {},
                this::adoptCreatedNote);
    }

    void rename() {
        requestAutosave();
    }

    private void startRename() {
        metadataInFlight = true;
        binding.statusText.setText(R.string.note_saving);
        NoteApiModels.TitleRequest request = new NoteApiModels.TitleRequest(
                UUID.randomUUID().toString(), localMetadataRevision, title());
        orbit.renameNote(current.id, request).thenAccept(note -> activity.runOnUiThread(() -> {
            metadataInFlight = false;
            current = note;
            localMetadataRevision = note.metadataRevision;
            library.upsert(note);
            persistWorkspace();
            binding.statusText.setText(R.string.note_saved_now);
            savePending = true;
            drainAutosave();
        })).exceptionally(failure -> {
            activity.runOnUiThread(() -> {
                metadataInFlight = false;
                binding.statusText.setText(R.string.note_offline_saved);
                screen.showRenameFailure(reloadDirectory);
            });
            return null;
        });
    }

    private void adoptCreatedNote(NoteApiModels.Note note) {
        current = note;
        serverBody = note.body;
        localBaseRevision = note.revision;
        localMetadataRevision = note.metadataRevision;
        drafts.clear(note.id);
        library.upsert(note);
        binding.attachButton.setEnabled(true);
        attachments.reset(note);
        editor = openEditor(note);
        workspace.persistNow(snapshot());
        creation.clear();
        persistWorkspace();
        binding.statusText.setText(R.string.note_saved_now);
        savePending = !body().equals(serverBody) || !title().equals(note.title);
        drainAutosave();
        finishReturn();
    }

    void confirmArchive() {
        archive.confirm();
    }

    void returnToLibrary() {
        if (current == null) {
            returnFromNewNote();
            return;
        }
        returnAfterSave = true;
        autosave.flush();
        requestAutosave();
        finishReturn();
    }

    private void returnFromNewNote() {
        if (title().isEmpty() && body().isBlank()) {
            leaveWorkspace();
        } else if (!title().isEmpty()) {
            returnAfterSave = true;
            create();
        } else {
            NoteDialogs.showUntitled(activity, this::leaveWorkspace);
        }
    }

    private void finishReturn() {
        if (!returnAfterSave || current == null) return;
        if (creation.inFlight() || metadataInFlight || bodyInFlight || needsReview) return;
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
        creation.clear();
        autosave.cancel();
        metadataInFlight = false;
        bodyInFlight = false;
        savePending = false;
        needsReview = false;
        serverBody = "";
    }

    void preserveDraftAndReturn() {
        if (current != null) drafts.save(current.id, body(), localBaseRevision);
        leaveWorkspace();
    }

    void abandon() {
        autosave.cancel();
        workspace.finish();
        closeEditor();
        attachments.clear();
        current = null;
        pendingRestore = null;
        restoringExisting = false;
        creation.clear();
        metadataInFlight = false;
        bodyInFlight = false;
        savePending = false;
        needsReview = false;
    }

    void useServerVersion() {
        if (current == null) return;
        needsReview = false;
        editor.acceptServer();
        screen.patchBody(serverBody);
        localBaseRevision = current.revision;
        drafts.clear(current.id);
        screen.showConflict(null);
        binding.statusText.setText(R.string.note_saved_now);
        persistWorkspace();
    }

    void keepMyVersion() {
        if (current == null) return;
        String sourceId = current.id;
        String operationId = UUID.nameUUIDFromBytes(
                ("fork:" + current.id + ":" + title() + ":" + body())
                        .getBytes(StandardCharsets.UTF_8)).toString();
        NoteApiModels.ForkRequest request =
                new NoteApiModels.ForkRequest(operationId, title(), body());
        binding.statusText.setText(R.string.note_saving);
        orbit.forkNote(sourceId, request).thenAccept(note -> activity.runOnUiThread(() -> {
            drafts.clear(sourceId);
            select(note);
            binding.statusText.setText(R.string.note_saved_now);
        })).exceptionally(failure -> {
            activity.runOnUiThread(() -> binding.statusText.setText(R.string.note_offline_saved));
            return null;
        });
    }

    void reviewAndMerge() {
        if (current == null || !needsReview) return;
        binding.statusText.setText(R.string.note_needs_review);
        screen.startMergeReview();
    }

    void finishMerge() {
        if (current == null || !needsReview) return;
        if (body().equals(serverBody)) {
            useServerVersion();
            return;
        }
        needsReview = false;
        localBaseRevision = current.revision;
        screen.showConflict(null);
        bodyInFlight = true;
        drafts.save(current.id, body(), localBaseRevision);
        editor.keepLocal(body());
        binding.statusText.setText(R.string.note_saving);
    }

    NoteSocketClient.EditorConnection openEditor(NoteApiModels.Note note) {
        if (!foreground) {
            resumeRequiresReload = true;
            return NoteSocketClient.EditorConnection.closed();
        }
        long generation = ++editorGeneration;
        return sockets.openEditor(
                note.id, note.body, note.revision,
                new NoteEditorEvents(activity, note.id, generation, this));
    }

    void closeEditor() {
        editorGeneration++;
        editor.close();
        editor = NoteSocketClient.EditorConnection.closed();
    }

    void persistWorkspace() {
        if (!screen.isEditorVisible()) return;
        workspace.persist(snapshot());
    }

    private NoteDraftStore.Workspace snapshot() {
        int start = Math.max(binding.bodyInput.getSelectionStart(), 0);
        int end = Math.max(binding.bodyInput.getSelectionEnd(), start);
        return NoteWorkspaceSnapshots.capture(
                current, binding.titleInput.getText().toString(), body(), serverBody,
                localBaseRevision, localMetadataRevision, creation.operationId(),
                start, end, screen.isPreviewing());
    }

    void pause() {
        foreground = false;
        autosave.flush();
        observers.cancel(workspaceSave);
        if (current != null && !body().equals(serverBody)) {
            drafts.save(current.id, body(), localBaseRevision);
        }
        if (screen.isEditorVisible()) workspace.persistNow(snapshot());
        bodyInFlight = false;
        metadataInFlight = false;
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
        autosave.cancel();
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

    String body() { return binding.bodyInput.getText().toString(); }

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
            needsReview = false;
            binding.statusText.setText(R.string.note_saved_now);
        } else {
            screen.showConflict(body);
            needsReview = true;
            binding.statusText.setText(R.string.note_needs_review);
        }
        persistWorkspace();
    }

    @Override public void applySaved(String body, int revision) {
        bodyInFlight = false;
        serverBody = body;
        current = NoteWorkspaceSnapshots.withBody(current, body, revision);
        localBaseRevision = revision;
        String local = body();
        if (local.equals(body)) {
            drafts.clear(current.id);
            screen.showConflict(null);
            screen.hideRecovery();
            needsReview = false;
            binding.statusText.setText(R.string.note_saved_now);
            library.upsert(current);
            finishReturn();
        } else {
            drafts.save(current.id, local, revision);
            savePending = true;
            binding.statusText.setText(R.string.note_saving);
        }
        persistWorkspace();
        drainAutosave();
    }

    @Override public void applyConflict(String body, int revision) {
        bodyInFlight = false;
        serverBody = body;
        current = NoteWorkspaceSnapshots.withBody(current, body, revision);
        screen.showConflict(body);
        needsReview = true;
        binding.statusText.setText(R.string.note_needs_review);
        persistWorkspace();
    }

    @Override public void applyFailure() {
        bodyInFlight = false;
        binding.statusText.setText(R.string.note_offline_saved);
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
