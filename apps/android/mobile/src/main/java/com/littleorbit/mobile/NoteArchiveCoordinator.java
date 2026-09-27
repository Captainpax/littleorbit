package com.littleorbit.mobile;

import com.google.android.material.dialog.MaterialAlertDialogBuilder;
import com.littleorbit.data.remote.NoteApiModels;
import com.littleorbit.data.repository.NoteDraftStore;
import com.littleorbit.data.repository.OrbitRepository;
import com.littleorbit.mobile.databinding.ActivityNotesBinding;
import java.util.UUID;
import java.util.function.Supplier;

/** Applies the reversible seven-day archive action to the selected document. */
final class NoteArchiveCoordinator {
    private final NotesActivity activity;
    private final OrbitRepository orbit;
    private final NoteDraftStore drafts;
    private final ActivityNotesBinding binding;
    private final SpaceLibraryViews library;
    private final Supplier<NoteApiModels.Note> selected;
    private final Runnable leave;
    private final Runnable reloadArchived;

    NoteArchiveCoordinator(
            NotesActivity activity, OrbitRepository orbit, NoteDraftStore drafts,
            ActivityNotesBinding binding, SpaceLibraryViews library,
            Supplier<NoteApiModels.Note> selected, Runnable leave,
            Runnable reloadArchived) {
        this.activity = activity;
        this.orbit = orbit;
        this.drafts = drafts;
        this.binding = binding;
        this.library = library;
        this.selected = selected;
        this.leave = leave;
        this.reloadArchived = reloadArchived;
    }

    void confirm() {
        if (selected.get() == null) return;
        new MaterialAlertDialogBuilder(activity)
                .setTitle(R.string.archive_note)
                .setMessage(R.string.archive_note_explanation)
                .setNegativeButton(android.R.string.cancel, null)
                .setPositiveButton(R.string.archive_action, (dialog, which) -> archive())
                .show();
    }

    private void archive() {
        NoteApiModels.Note current = selected.get();
        if (current == null) return;
        NoteApiModels.ArchiveRequest request = new NoteApiModels.ArchiveRequest(
                UUID.randomUUID().toString(), current.metadataRevision);
        AsyncUi.observe(activity, orbit.archiveNote(current.id, request), binding.statusText, note -> {
            drafts.clear(note.id);
            library.remove(note.id);
            leave.run();
            reloadArchived.run();
        });
    }
}
