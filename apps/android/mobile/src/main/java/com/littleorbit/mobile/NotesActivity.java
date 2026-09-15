package com.littleorbit.mobile;

import android.content.Intent;
import android.os.Bundle;
import android.os.Handler;
import android.os.Looper;
import androidx.activity.result.ActivityResultLauncher;
import androidx.activity.result.contract.ActivityResultContracts;
import com.littleorbit.data.remote.NoteApiModels;
import com.littleorbit.data.remote.NoteSocketClient;
import com.littleorbit.data.repository.NoteDraftStore;
import com.littleorbit.data.repository.OrbitRepository;
import com.littleorbit.mobile.databinding.ActivityNotesBinding;
import dagger.hilt.android.AndroidEntryPoint;
import java.util.ArrayList;
import java.util.HashSet;
import java.util.List;
import java.util.Set;
import java.util.UUID;
import javax.inject.Inject;

/** Library-first Our Space destination and document-directory coordinator. */
@AndroidEntryPoint
public final class NotesActivity extends OrbitShellActivity {
    /** Opens one authorized document from a private notification. */
    public static final String EXTRA_NOTE_ID = "open_note_id";
    private static final long DIRECTORY_REFRESH_MILLIS = 5_000;
    @Inject OrbitRepository orbit;
    @Inject NoteDraftStore drafts;
    @Inject NoteSocketClient sockets;
    private NoteAttachmentController attachments;
    private final ActivityResultLauncher<String[]> filePicker = registerForActivityResult(
            new ActivityResultContracts.OpenDocument(), uri -> attachments.chosen(uri));
    private ActivityNotesBinding binding;
    private NoteEditorView screen;
    private MarkdownEditorTools editorTools;
    private SpaceLibraryViews library;
    private NoteWorkspaceController workspace;
    private NoteDocumentSession document;
    private String notificationNoteId;
    private Set<String> activeNoteIds = Set.of();
    private final Handler directoryRefreshes = new Handler(Looper.getMainLooper());
    private final Runnable directoryRefresh = this::refreshDirectory;
    private boolean foreground;
    private boolean directoryLoading;
    private boolean directoryRefreshAllowed = true;

    @Override protected void onCreate(Bundle savedState) {
        super.onCreate(savedState);
        binding = ActivityNotesBinding.inflate(getLayoutInflater());
        setContentView(binding.getRoot());
        MarkdownRenderer markdown = new MarkdownRenderer(
                this, orbit, attachment -> attachments.openPreview(attachment));
        screen = new NoteEditorView(binding, markdown);
        editorTools = new MarkdownEditorTools(this, binding.bodyInput);
        workspace = new NoteWorkspaceController(drafts, savedState);
        library = new SpaceLibraryViews(
                this, binding.noteListContainer, binding.archivedNotesContainer,
                binding.searchInput, note -> document.select(note), this::restore);
        document = new NoteDocumentSession(
                this, orbit, drafts, sockets, binding, screen, library, workspace,
                this::load, this::loadArchived);
        attachments = new NoteAttachmentController(
                this, orbit, binding, filePicker, document::current, screen::isPreviewing,
                screen::renderPreview, markdown, editorTools);
        document.attach(attachments);
        bindActions();
        document.bindEditors();
        screen.showLibrary();
        if (workspace.restored().isPresent()) {
            document.restoreWorkspace(workspace.restored().orElseThrow());
        } else if (savedState == null) {
            notificationNoteId = getIntent().getStringExtra(EXTRA_NOTE_ID);
        }
        load();
    }

    @Override protected void onNewIntent(Intent intent) {
        super.onNewIntent(intent);
        setIntent(intent);
        document.abandon();
        notificationNoteId = intent.getStringExtra(EXTRA_NOTE_ID);
        screen.showLibrary();
        load();
    }

    @Override protected void onResume() {
        super.onResume();
        foreground = true;
        directoryRefreshAllowed = true;
        document.resume();
        if (!screen.isEditorVisible()) load();
        scheduleDirectoryRefresh();
    }

    @Override protected OrbitDestination orbitDestination() {
        return OrbitDestination.SPACE;
    }

    private void bindActions() {
        binding.createButton.setOnClickListener(ignored -> document.newNote());
        binding.syncButton.setOnClickListener(ignored -> document.sync());
        binding.archiveButton.setOnClickListener(ignored -> document.confirmArchive());
        binding.backToLibrary.setOnClickListener(ignored -> document.returnToLibrary());
        binding.useServerButton.setOnClickListener(ignored -> document.useServerVersion());
        binding.keepMyVersionButton.setOnClickListener(ignored -> document.keepMyVersion());
        binding.libraryRetryButton.setOnClickListener(ignored -> load());
        binding.boldButton.setOnClickListener(ignored -> editorTools.wrap("**", "**"));
        binding.italicButton.setOnClickListener(ignored -> editorTools.wrap("_", "_"));
        binding.headingButton.setOnClickListener(ignored -> editorTools.insert("## "));
        binding.listButton.setOnClickListener(ignored -> editorTools.insert("- "));
        binding.checkButton.setOnClickListener(ignored -> editorTools.insert("- [ ] "));
        binding.linkButton.setOnClickListener(ignored -> editorTools.wrap("[", "](https://)"));
        binding.attachButton.setOnClickListener(ignored -> attachments.choose());
        binding.formattingMoreButton.setOnClickListener(editorTools::showMore);
    }

    private void load() {
        if (directoryLoading) return;
        directoryLoading = true;
        binding.libraryRetryButton.setOnClickListener(ignored -> load());
        binding.libraryRetryButton.setEnabled(false);
        orbit.notes().whenComplete((notes, failure) -> runOnUiThread(() -> {
            directoryLoading = false;
            binding.libraryRetryButton.setEnabled(true);
            if (failure != null) {
                if (SafeRequestFailure.relationshipInactive(failure)) {
                    directoryRefreshAllowed = false;
                    document.relationshipInactive();
                } else {
                    document.showLoadFailure();
                }
                return;
            }
            directoryRefreshAllowed = true;
            screen.hideLibraryFailure();
            binding.libraryPresenceText.setText(R.string.note_presence_solo);
            library.setNotes(notes);
            activeNoteIds = ids(notes);
            updateNoteDirectory(notes);
            loadArchived();
            if (document.hasPendingRestore()) document.reconcileRestore(notes);
            else restoreNotificationTarget(notes);
        }));
    }

    private void restoreNotificationTarget(List<NoteApiModels.Note> notes) {
        if (notificationNoteId == null) return;
        String wanted = notificationNoteId;
        notificationNoteId = null;
        notes.stream().filter(note -> wanted.equals(note.id)).findFirst()
                .ifPresentOrElse(document::select, screen::showLibraryFailure);
    }

    private void updateNoteDirectory(List<NoteApiModels.Note> notes) {
        ArrayList<ContextAction> actions = new ArrayList<>();
        actions.add(new ContextAction(getString(R.string.refresh_shared_documents), this::load));
        actions.add(new ContextAction(getString(R.string.create_space_document), document::newNote));
        actions.add(new ContextAction(getString(R.string.search_space), document::returnToLibrary));
        for (NoteApiModels.Note note : notes) {
            if (note.archivedAt == null && actions.size() < 10) {
                actions.add(new ContextAction(note.title, () -> document.select(note)));
            }
        }
        setOrbitContextActions(actions);
    }

    private void loadArchived() {
        orbit.archivedNotes().thenAccept(notes -> runOnUiThread(() -> {
            library.showArchived(notes);
            Set<String> retained = new HashSet<>(activeNoteIds);
            retained.addAll(ids(notes));
            attachments.retainOfflineNotes(retained);
        })).exceptionally(failure -> null);
    }

    private static Set<String> ids(List<NoteApiModels.Note> notes) {
        Set<String> ids = new HashSet<>();
        for (NoteApiModels.Note note : notes) ids.add(note.id);
        return Set.copyOf(ids);
    }

    private void restore(NoteApiModels.Note note) {
        NoteApiModels.ArchiveRequest request = new NoteApiModels.ArchiveRequest(
                UUID.randomUUID().toString(), note.metadataRevision);
        orbit.restoreNote(note.id, request).whenComplete((restored, failure) ->
                runOnUiThread(() -> {
                    if (failure != null) {
                        screen.showLibraryFailure();
                        return;
                    }
                    screen.hideLibraryFailure();
                    library.upsert(restored);
                    loadArchived();
                }));
    }

    @Override protected void onPause() {
        foreground = false;
        directoryRefreshes.removeCallbacks(directoryRefresh);
        document.pause();
        super.onPause();
    }

    @Override protected void onDestroy() {
        directoryRefreshes.removeCallbacks(directoryRefresh);
        document.destroy();
        super.onDestroy();
    }

    @Override protected void onSaveInstanceState(Bundle state) {
        document.saveState(state);
        super.onSaveInstanceState(state);
    }

    private void refreshDirectory() {
        if (!foreground || !directoryRefreshAllowed) return;
        if (!screen.isEditorVisible()) load();
        scheduleDirectoryRefresh();
    }

    private void scheduleDirectoryRefresh() {
        directoryRefreshes.removeCallbacks(directoryRefresh);
        if (foreground && directoryRefreshAllowed) {
            directoryRefreshes.postDelayed(directoryRefresh, DIRECTORY_REFRESH_MILLIS);
        }
    }
}
