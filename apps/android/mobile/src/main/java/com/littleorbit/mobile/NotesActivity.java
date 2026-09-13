package com.littleorbit.mobile;

import android.net.Uri;
import android.os.Bundle;
import android.os.Handler;
import android.os.Looper;
import android.text.Editable;
import android.text.Selection;
import android.text.TextWatcher;
import android.view.View;
import android.widget.PopupMenu;
import androidx.activity.result.ActivityResultLauncher;
import androidx.activity.result.contract.ActivityResultContracts;
import com.littleorbit.data.remote.NoteApiModels;
import com.littleorbit.data.remote.NoteSocketClient;
import com.littleorbit.data.repository.NoteDraftStore;
import com.littleorbit.data.repository.OrbitRepository;
import com.littleorbit.domain.TextPatch;
import com.littleorbit.mobile.databinding.ActivityNotesBinding;
import dagger.hilt.android.AndroidEntryPoint;
import java.util.UUID;
import javax.inject.Inject;

/** Library-first Our Space workspace with Markdown, private files, and stable live editing. */
@AndroidEntryPoint
public final class NotesActivity extends OrbitShellActivity {
    @Inject OrbitRepository orbit;
    @Inject NoteDraftStore drafts;
    @Inject NoteSocketClient sockets;
    private final Handler debounce = new Handler(Looper.getMainLooper());
    private final ActivityResultLauncher<String[]> filePicker = registerForActivityResult(
            new ActivityResultContracts.OpenDocument(), this::attachmentChosen);
    private ActivityNotesBinding binding;
    private MarkdownRenderer markdown;
    private NoteAttachmentViews attachmentViews;
    private NoteAttachmentUploadCoordinator attachmentUploads;
    private SpaceLibraryViews library;
    private NoteApiModels.Note current;
    private String serverBody = "";
    private boolean rendering;
    private boolean returnAfterSave;
    private int attachmentPolls;
    private NoteSocketClient.EditorConnection editor = NoteSocketClient.EditorConnection.closed();
    private final Runnable bodySave = this::sync;
    private final Runnable titleSave = this::rename;

    @Override protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        binding = ActivityNotesBinding.inflate(getLayoutInflater());
        setContentView(binding.getRoot());
        markdown = new MarkdownRenderer(this);
        attachmentViews = new NoteAttachmentViews(
                this, orbit, binding.attachmentContainer, binding.statusText,
                this::reloadAttachments, this::insertAttachmentLink,
                ignored -> chooseAttachment());
        attachmentUploads = new NoteAttachmentUploadCoordinator(this, orbit, binding.statusText);
        library = new SpaceLibraryViews(
                this, binding.noteListContainer, binding.archivedNotesContainer,
                binding.searchInput, this::select, this::restore);
        bindActions();
        bindEditors();
        showLibrary();
        load();
    }

    private void bindActions() {
        binding.createButton.setOnClickListener(view -> newNote());
        binding.syncButton.setOnClickListener(view -> sync());
        binding.archiveButton.setOnClickListener(view -> confirmArchive());
        binding.backToLibrary.setOnClickListener(view -> returnToLibrary());
        binding.useServerButton.setOnClickListener(view -> useServerVersion());
        binding.keepMyVersionButton.setOnClickListener(view -> keepMyVersion());
        binding.editTab.setOnClickListener(view -> showEdit());
        binding.previewTab.setOnClickListener(view -> showPreview());
        binding.boldButton.setOnClickListener(view -> wrapSelection("**", "**"));
        binding.italicButton.setOnClickListener(view -> wrapSelection("_", "_"));
        binding.headingButton.setOnClickListener(view -> insertAtCursor("## "));
        binding.listButton.setOnClickListener(view -> insertAtCursor("- "));
        binding.checkButton.setOnClickListener(view -> insertAtCursor("- [ ] "));
        binding.linkButton.setOnClickListener(view -> wrapSelection("[", "](https://)"));
        binding.attachButton.setOnClickListener(view -> chooseAttachment());
        binding.formattingMoreButton.setOnClickListener(this::showFormattingMenu);
    }

    private void showFormattingMenu(View anchor) {
        PopupMenu menu = new PopupMenu(this, anchor);
        menu.getMenu().add(0, 1, 0, R.string.format_numbered_list);
        menu.getMenu().add(0, 2, 1, R.string.format_quote);
        menu.getMenu().add(0, 3, 2, R.string.format_code);
        menu.getMenu().add(0, 4, 3, R.string.format_table);
        menu.getMenu().add(0, 5, 4, R.string.format_strikethrough);
        menu.getMenu().add(0, 6, 5, R.string.format_divider);
        menu.setOnMenuItemClickListener(item -> applyExtraFormat(item.getItemId()));
        menu.show();
    }

    private boolean applyExtraFormat(int itemId) {
        switch (itemId) {
            case 1 -> insertAtCursor("1. ");
            case 2 -> insertAtCursor("> ");
            case 3 -> wrapSelection("`", "`");
            case 4 -> insertAtCursor("| Column | Column |\n| --- | --- |\n|  |  |\n");
            case 5 -> wrapSelection("~~", "~~");
            case 6 -> insertAtCursor("\n---\n");
            default -> { return false; }
        }
        return true;
    }

    @Override protected OrbitDestination orbitDestination() {
        return OrbitDestination.SPACE;
    }

    private void bindEditors() {
        binding.bodyInput.addTextChangedListener(watcher(() -> {
            if (current == null) return;
            String body = binding.bodyInput.getText().toString();
            drafts.save(current.id, body, current.revision);
            debounce.removeCallbacks(bodySave);
            debounce.postDelayed(bodySave, 750);
        }));
        binding.titleInput.addTextChangedListener(watcher(() -> {
            if (current == null) return;
            debounce.removeCallbacks(titleSave);
            debounce.postDelayed(titleSave, 750);
        }));
    }

    private TextWatcher watcher(Runnable changed) {
        return new TextWatcher() {
            @Override public void beforeTextChanged(
                    CharSequence value, int start, int count, int after) {}
            @Override public void onTextChanged(
                    CharSequence value, int start, int before, int count) {}
            @Override public void afterTextChanged(Editable value) {
                if (!rendering) changed.run();
            }
        };
    }

    private void load() {
        orbit.notes().whenComplete((notes, failure) -> runOnUiThread(() -> {
            if (failure != null) {
                binding.libraryPresenceText.setText(R.string.request_failed);
                return;
            }
            binding.libraryPresenceText.setText(R.string.note_presence_solo);
            library.setNotes(notes);
            updateNoteDirectory(notes);
            loadArchived();
        }));
    }

    private void updateNoteDirectory(java.util.List<NoteApiModels.Note> notes) {
        java.util.ArrayList<ContextAction> actions = new java.util.ArrayList<>();
        actions.add(new ContextAction(getString(R.string.create_space_document), this::newNote));
        actions.add(new ContextAction(getString(R.string.search_space), this::returnToLibrary));
        for (NoteApiModels.Note note : notes) {
            if (note.archivedAt == null && actions.size() < 10) {
                actions.add(new ContextAction(note.title, () -> select(note)));
            }
        }
        setOrbitContextActions(actions);
    }

    private void loadArchived() {
        orbit.archivedNotes().thenAccept(notes ->
                runOnUiThread(() -> library.showArchived(notes))).exceptionally(failure -> null);
    }

    private void select(NoteApiModels.Note note) {
        editor.close();
        current = note;
        serverBody = note.body;
        NoteDraftStore.Draft draft = drafts.read(note.id).orElse(null);
        renderInitial(note.title, draft == null ? note.body : draft.body());
        boolean conflict = draft != null && draft.baseRevision() != note.revision;
        showConflict(conflict ? note.body : null);
        binding.statusText.setText(conflict ? R.string.note_reconcile : R.string.note_ready);
        binding.attachButton.setEnabled(true);
        attachmentPolls = 0;
        editor = sockets.openEditor(note.id, note.body, note.revision, new EditorResult(note.id));
        if (draft != null && !conflict) {
            editor.update(draft.body());
            binding.statusText.setText(R.string.syncing_note);
        }
        showEditor();
        loadAttachments(note.id);
    }

    private void renderInitial(String title, String body) {
        rendering = true;
        binding.titleInput.setText(title);
        binding.bodyInput.setText(body);
        Selection.setSelection(binding.bodyInput.getText(), binding.bodyInput.length());
        rendering = false;
    }

    private void newNote() {
        editor.close();
        editor = NoteSocketClient.EditorConnection.closed();
        current = null;
        serverBody = "";
        renderInitial("", "");
        showConflict(null);
        binding.attachmentContainer.removeAllViews();
        binding.attachButton.setEnabled(false);
        binding.statusText.setText(R.string.note_new_hint);
        showEditor();
        binding.titleInput.requestFocus();
    }

    private void create() {
        String title = binding.titleInput.getText().toString().trim();
        if (title.isEmpty()) {
            binding.statusText.setText(R.string.complete_required_fields);
            return;
        }
        NoteApiModels.CreateRequest request = new NoteApiModels.CreateRequest(
                UUID.randomUUID().toString(), title, binding.bodyInput.getText().toString());
        AsyncUi.observe(this, orbit.createNote(request), binding.statusText, note -> {
            drafts.clear(note.id);
            library.upsert(note);
            select(note);
        });
    }

    private void sync() {
        if (rendering) return;
        if (current == null) {
            if (!binding.titleInput.getText().toString().trim().isEmpty()) create();
            return;
        }
        String body = binding.bodyInput.getText().toString();
        if (body.equals(serverBody)) {
            binding.statusText.setText(R.string.note_synced);
            finishReturn();
            return;
        }
        drafts.save(current.id, body, current.revision);
        editor.update(body);
        binding.statusText.setText(R.string.syncing_note);
    }

    private void rename() {
        if (current == null) return;
        String title = binding.titleInput.getText().toString().trim();
        if (title.isEmpty() || title.equals(current.title)) return;
        NoteApiModels.TitleRequest request = new NoteApiModels.TitleRequest(
                UUID.randomUUID().toString(), current.metadataRevision, title);
        orbit.renameNote(current.id, request).thenAccept(note -> runOnUiThread(() -> {
            current = note;
            library.upsert(note);
        })).exceptionally(failure -> {
            runOnUiThread(() -> binding.statusText.setText(R.string.remote_change_conflict));
            return null;
        });
    }

    private void archive() {
        if (current == null) return;
        NoteApiModels.ArchiveRequest request = new NoteApiModels.ArchiveRequest(
                UUID.randomUUID().toString(), current.metadataRevision);
        AsyncUi.observe(this, orbit.archiveNote(current.id, request), binding.statusText, note -> {
            drafts.clear(note.id);
            library.remove(note.id);
            current = null;
            editor.close();
            showLibrary();
            loadArchived();
        });
    }

    private void confirmArchive() {
        if (current == null) return;
        new com.google.android.material.dialog.MaterialAlertDialogBuilder(this)
                .setTitle(R.string.archive_note)
                .setMessage(R.string.archive_note_explanation)
                .setNegativeButton(android.R.string.cancel, null)
                .setPositiveButton(R.string.archive_action, (dialog, which) -> archive())
                .show();
    }

    private void restore(NoteApiModels.Note note) {
        NoteApiModels.ArchiveRequest request = new NoteApiModels.ArchiveRequest(
                UUID.randomUUID().toString(), note.metadataRevision);
        orbit.restoreNote(note.id, request).whenComplete((restored, failure) ->
                runOnUiThread(() -> {
                    if (failure != null) {
                        binding.libraryPresenceText.setText(R.string.request_failed);
                        return;
                    }
                    binding.libraryPresenceText.setText(R.string.note_presence_solo);
                    library.upsert(restored);
                    loadArchived();
                }));
    }

    private void returnToLibrary() {
        if (current == null || binding.bodyInput.getText().toString().equals(serverBody)) {
            editor.close();
            showLibrary();
            return;
        }
        returnAfterSave = true;
        sync();
    }

    private void finishReturn() {
        if (!returnAfterSave) return;
        returnAfterSave = false;
        editor.close();
        showLibrary();
    }

    private void useServerVersion() {
        if (current == null) return;
        editor.acceptServer();
        patchEditor(serverBody);
        drafts.clear(current.id);
        showConflict(null);
        binding.statusText.setText(R.string.note_ready);
    }

    private void keepMyVersion() {
        if (current == null) return;
        showConflict(null);
        editor.keepLocal(binding.bodyInput.getText().toString());
        binding.statusText.setText(R.string.syncing_note);
    }

    private void showConflict(String serverVersion) {
        boolean visible = serverVersion != null;
        binding.conflictCard.setVisibility(visible ? View.VISIBLE : View.GONE);
        if (visible) binding.serverVersionText.setText(serverVersion);
    }

    private void showEdit() {
        binding.bodyInput.setVisibility(View.VISIBLE);
        binding.formattingScroll.setVisibility(View.VISIBLE);
        binding.previewText.setVisibility(View.GONE);
        binding.remoteImageNotice.setVisibility(View.GONE);
        binding.editTab.setEnabled(false);
        binding.previewTab.setEnabled(true);
    }

    private void showPreview() {
        String body = binding.bodyInput.getText().toString();
        markdown.render(binding.previewText, body);
        binding.bodyInput.setVisibility(View.GONE);
        binding.formattingScroll.setVisibility(View.GONE);
        binding.previewText.setVisibility(View.VISIBLE);
        binding.remoteImageNotice.setVisibility(
                body.matches("(?s).*?!\\[[^]]*]\\(https?://.*")
                        ? View.VISIBLE : View.GONE);
        binding.editTab.setEnabled(true);
        binding.previewTab.setEnabled(false);
    }

    private void wrapSelection(String before, String after) {
        Editable text = binding.bodyInput.getText();
        int start = Math.max(binding.bodyInput.getSelectionStart(), 0);
        int end = Math.max(binding.bodyInput.getSelectionEnd(), start);
        String selected = text.subSequence(start, end).toString();
        text.replace(start, end, before + selected + after);
        Selection.setSelection(text, start + before.length(), start + before.length() + selected.length());
    }

    private void insertAtCursor(String value) {
        Editable text = binding.bodyInput.getText();
        int position = Math.max(binding.bodyInput.getSelectionStart(), 0);
        text.insert(position, value);
        Selection.setSelection(text, position + value.length());
    }

    private void chooseAttachment() {
        if (current == null) {
            binding.statusText.setText(R.string.save_before_attaching);
            return;
        }
        filePicker.launch(NoteAttachmentUploadCoordinator.TYPES);
    }

    private void attachmentChosen(Uri uri) {
        if (uri == null || current == null) return;
        attachmentUploads.upload(uri, current, this::attachmentUploaded);
    }

    private void attachmentUploaded(
            String noteId, NoteApiModels.Attachment attachment) {
        if (current == null || !noteId.equals(current.id)) return;
        binding.statusText.setText(R.string.attachment_scanning_status);
        attachmentPolls = 0;
        loadAttachments(noteId);
    }

    private void insertAttachmentLink(NoteApiModels.Attachment attachment) {
        String safeName = attachment.fileName.replace("]", "");
        String link = attachment.mediaType.startsWith("image/")
                ? "![" + safeName + "](attachment://" + attachment.id + ")"
                : "[" + safeName + "](attachment://" + attachment.id + ")";
        insertAtCursor((binding.bodyInput.length() == 0 ? "" : "\n") + link + "\n");
    }

    private void loadAttachments(String noteId) {
        orbit.noteAttachments(noteId).thenAccept(items -> runOnUiThread(() -> {
            if (current == null || !noteId.equals(current.id)) return;
            attachmentViews.show(noteId, items);
            boolean processing = items.stream().anyMatch(item ->
                    "uploading".equals(item.status)
                            || "pending_scan".equals(item.status)
                            || "scanning".equals(item.status));
            if (processing && attachmentPolls++ < 20) {
                debounce.postDelayed(() -> loadAttachments(noteId), 3000);
            }
        })).exceptionally(failure -> null);
    }

    private void reloadAttachments(String noteId) {
        if (current == null || !noteId.equals(current.id)) return;
        attachmentPolls = 0;
        loadAttachments(noteId);
    }

    private void showEditor() {
        binding.libraryScroll.setVisibility(View.GONE);
        binding.editorScroll.setVisibility(View.VISIBLE);
        showEdit();
    }

    private void showLibrary() {
        binding.editorScroll.setVisibility(View.GONE);
        binding.formattingScroll.setVisibility(View.GONE);
        binding.libraryScroll.setVisibility(View.VISIBLE);
    }

    private void patchEditor(String body) {
        Editable editable = binding.bodyInput.getText();
        TextPatch patch = TextPatch.between(editable.toString(), body);
        if (patch.isEmpty()) return;
        int startSelection = Math.max(binding.bodyInput.getSelectionStart(), 0);
        int endSelection = Math.max(binding.bodyInput.getSelectionEnd(), startSelection);
        rendering = true;
        editable.replace(patch.start(), patch.end(), patch.replacement());
        Selection.setSelection(
                editable, patch.mapOffset(startSelection), patch.mapOffset(endSelection));
        rendering = false;
    }

    @Override protected void onPause() {
        debounce.removeCallbacks(bodySave);
        debounce.removeCallbacks(titleSave);
        if (current != null && !binding.bodyInput.getText().toString().equals(serverBody)) {
            drafts.save(current.id, binding.bodyInput.getText().toString(), current.revision);
        }
        super.onPause();
    }

    @Override protected void onDestroy() {
        editor.close();
        debounce.removeCallbacksAndMessages(null);
        super.onDestroy();
    }

    private NoteApiModels.Note withBody(String body, int revision) {
        return new NoteApiModels.Note(current.id, current.title, body, revision,
                current.metadataRevision, current.updatedAt, current.archivedAt, current.purgeAfter);
    }

    private final class EditorResult implements NoteSocketClient.Listener {
        private final String noteId;

        EditorResult(String noteId) {
            this.noteId = noteId;
        }

        private boolean active() {
            return current != null && noteId.equals(current.id);
        }

        @Override public void onRemoteVersion(String body, int revision) {
            runOnUiThread(() -> applyRemote(body, revision));
        }

        @Override public void onSaved(String body, int revision) {
            runOnUiThread(() -> applySaved(body, revision));
        }

        @Override public void onConflict(String body, int revision) {
            runOnUiThread(() -> {
                if (!active()) return;
                serverBody = body;
                current = withBody(body, revision);
                showConflict(body);
                binding.statusText.setText(R.string.note_reconcile);
            });
        }

        @Override public void onFailure() {
            runOnUiThread(() -> {
                if (active()) binding.statusText.setText(R.string.note_draft_preserved);
            });
        }

        @Override public void onPresence(int editors) {
            runOnUiThread(() -> {
                if (!active()) return;
                int label = editors > 1
                        ? R.string.note_presence_together : R.string.note_presence_solo;
                binding.presenceText.setText(label);
                binding.libraryPresenceText.setText(label);
            });
        }

        private void applyRemote(String body, int revision) {
            if (!active()) return;
            String local = binding.bodyInput.getText().toString();
            String priorServer = serverBody;
            serverBody = body;
            current = withBody(body, revision);
            if (local.equals(priorServer) || local.equals(body)) {
                patchEditor(body);
                drafts.clear(current.id);
                binding.statusText.setText(R.string.note_synced);
            } else {
                showConflict(body);
                binding.statusText.setText(R.string.note_reconcile);
            }
        }

        private void applySaved(String body, int revision) {
            if (!active()) return;
            serverBody = body;
            current = withBody(body, revision);
            String local = binding.bodyInput.getText().toString();
            if (local.equals(body)) {
                drafts.clear(current.id);
                showConflict(null);
                binding.statusText.setText(R.string.note_synced);
                library.upsert(current);
                finishReturn();
            } else {
                drafts.save(current.id, local, revision);
                binding.statusText.setText(R.string.syncing_note);
            }
        }
    }

    private int dp(int value) {
        return Math.round(value * getResources().getDisplayMetrics().density);
    }
}
