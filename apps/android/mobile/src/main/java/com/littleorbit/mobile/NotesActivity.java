package com.littleorbit.mobile;

import android.os.Bundle;
import android.os.Handler;
import android.os.Looper;
import android.text.Editable;
import android.text.TextWatcher;
import android.view.View;
import com.google.android.material.button.MaterialButton;
import com.littleorbit.data.remote.ApiModels;
import com.littleorbit.data.remote.NoteApiModels;
import com.littleorbit.data.remote.NoteSocketClient;
import com.littleorbit.data.repository.NoteDraftStore;
import com.littleorbit.data.repository.OrbitRepository;
import com.littleorbit.mobile.databinding.ActivityNotesBinding;
import dagger.hilt.android.AndroidEntryPoint;
import java.util.List;
import java.util.UUID;
import javax.inject.Inject;

/** Multi-note live workspace with encrypted drafts and explicit conflict choices. */
@AndroidEntryPoint
public final class NotesActivity extends InsetAwareActivity {
    @Inject OrbitRepository orbit;
    @Inject NoteDraftStore drafts;
    @Inject NoteSocketClient sockets;
    private final Handler debounce = new Handler(Looper.getMainLooper());
    private ActivityNotesBinding binding;
    private NoteApiModels.Note current;
    private String serverBody = "";
    private boolean rendering;
    private NoteSocketClient.Connection syncConnection = () -> {};
    private NoteSocketClient.Connection liveConnection = () -> {};
    private final Runnable bodySave = this::sync;
    private final Runnable titleSave = this::rename;

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        binding = ActivityNotesBinding.inflate(getLayoutInflater());
        setContentView(binding.getRoot());
        binding.createButton.setOnClickListener(view -> newNote());
        binding.syncButton.setOnClickListener(view -> sync());
        binding.archiveButton.setOnClickListener(view -> archive());
        binding.useServerButton.setOnClickListener(view -> useServerVersion());
        binding.keepMyVersionButton.setOnClickListener(view -> keepMyVersion());
        bindDebouncedEditors();
        load();
    }

    private void bindDebouncedEditors() {
        binding.bodyInput.addTextChangedListener(watcher(() -> {
            if (current == null) return;
            drafts.save(current.id, binding.bodyInput.getText().toString(), current.revision);
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
        AsyncUi.observe(this, orbit.notes(), binding.statusText, this::showNotes);
        orbit.archivedNotes().thenAccept(notes -> runOnUiThread(() -> showArchived(notes)))
                .exceptionally(failure -> null);
    }

    private void showNotes(List<NoteApiModels.Note> notes) {
        binding.noteListContainer.removeAllViews();
        for (NoteApiModels.Note note : notes) {
            binding.noteListContainer.addView(noteButton(note, false));
        }
        if (notes.isEmpty()) {
            newNote();
            binding.statusText.setText(R.string.no_notes);
            return;
        }
        NoteApiModels.Note selected = current == null ? notes.get(0) : notes.stream()
                .filter(note -> note.id.equals(current.id)).findFirst().orElse(notes.get(0));
        select(selected);
    }

    private void showArchived(List<NoteApiModels.Note> notes) {
        binding.archivedNotesContainer.removeAllViews();
        for (NoteApiModels.Note note : notes) {
            binding.archivedNotesContainer.addView(noteButton(note, true));
        }
    }

    private MaterialButton noteButton(NoteApiModels.Note note, boolean archived) {
        MaterialButton button = new MaterialButton(
                this, null, com.google.android.material.R.attr.materialButtonOutlinedStyle);
        button.setText(archived ? getString(R.string.restore_note_named, note.title) : note.title);
        button.setOnClickListener(view -> {
            if (archived) restore(note); else select(note);
        });
        button.setContentDescription(button.getText());
        return button;
    }

    private void select(NoteApiModels.Note note) {
        closeSockets();
        current = note;
        serverBody = note.body;
        NoteDraftStore.Draft draft = drafts.read(note.id).orElse(null);
        rendering = true;
        binding.titleInput.setText(note.title);
        binding.bodyInput.setText(draft == null ? note.body : draft.body());
        rendering = false;
        boolean conflict = draft != null && draft.baseRevision() != note.revision;
        showConflict(conflict ? note.body : null);
        binding.statusText.setText(conflict ? R.string.note_reconcile : R.string.note_ready);
        binding.archiveButton.setVisibility(View.VISIBLE);
        liveConnection = sockets.observe(note.id, new LiveResult(note.id));
    }

    private void newNote() {
        closeSockets();
        current = null;
        serverBody = "";
        rendering = true;
        binding.titleInput.setText("");
        binding.bodyInput.setText("");
        rendering = false;
        showConflict(null);
        binding.archiveButton.setVisibility(View.GONE);
        binding.statusText.setText(R.string.note_new_hint);
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
            current = note;
            drafts.clear(note.id);
            load();
        });
    }

    private void sync() {
        if (rendering) return;
        if (current == null) {
            if (!binding.titleInput.getText().toString().trim().isEmpty()) create();
            return;
        }
        String localBody = binding.bodyInput.getText().toString();
        if (localBody.equals(serverBody)) return;
        drafts.save(current.id, localBody, current.revision);
        syncConnection.close();
        syncConnection = sockets.replace(current.id, current.revision, serverBody,
                localBody, new SocketResult(current.id));
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
            load();
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
            newNote();
            load();
        });
    }

    private void restore(NoteApiModels.Note note) {
        NoteApiModels.ArchiveRequest request = new NoteApiModels.ArchiveRequest(
                UUID.randomUUID().toString(), note.metadataRevision);
        AsyncUi.observe(this, orbit.restoreNote(note.id, request), binding.statusText, restored -> {
            current = restored;
            load();
        });
    }

    private void useServerVersion() {
        if (current == null) return;
        rendering = true;
        binding.bodyInput.setText(serverBody);
        rendering = false;
        drafts.clear(current.id);
        showConflict(null);
        binding.statusText.setText(R.string.note_ready);
    }

    private void keepMyVersion() {
        if (current == null) return;
        showConflict(null);
        sync();
    }

    private void showConflict(String serverVersion) {
        boolean visible = serverVersion != null;
        binding.conflictCard.setVisibility(visible ? View.VISIBLE : View.GONE);
        if (visible) binding.serverVersionText.setText(serverVersion);
    }

    @Override
    protected void onPause() {
        debounce.removeCallbacksAndMessages(null);
        if (current != null && !binding.bodyInput.getText().toString().equals(serverBody)) {
            drafts.save(current.id, binding.bodyInput.getText().toString(), current.revision);
        }
        super.onPause();
    }

    @Override
    protected void onDestroy() {
        closeSockets();
        super.onDestroy();
    }

    private void closeSockets() {
        syncConnection.close();
        liveConnection.close();
        syncConnection = () -> {};
        liveConnection = () -> {};
    }

    private NoteApiModels.Note withBody(String body, int revision) {
        return new NoteApiModels.Note(current.id, current.title, body, revision,
                current.metadataRevision, current.updatedAt, current.archivedAt, current.purgeAfter);
    }

    private class SocketResult implements NoteSocketClient.Listener {
        private final String noteId;

        SocketResult(String noteId) { this.noteId = noteId; }

        boolean isActive() { return current != null && noteId.equals(current.id); }

        @Override public void onSynced(String body, int revision) {
            runOnUiThread(() -> {
                if (!isActive()) return;
                serverBody = body;
                current = withBody(body, revision);
                drafts.clear(current.id);
                showConflict(null);
                binding.statusText.setText(R.string.note_synced);
            });
        }
        @Override public void onConflict(String body, int revision) {
            runOnUiThread(() -> {
                if (!isActive()) return;
                serverBody = body;
                current = withBody(body, revision);
                showConflict(body);
                binding.statusText.setText(R.string.note_reconcile);
            });
        }
        @Override public void onFailure() {
            runOnUiThread(() -> {
                if (isActive()) binding.statusText.setText(R.string.note_draft_preserved);
            });
        }
    }

    private final class LiveResult extends SocketResult {
        LiveResult(String noteId) { super(noteId); }

        @Override public void onSynced(String body, int revision) {
            runOnUiThread(() -> {
                if (isActive()) applyLiveVersion(body, revision);
            });
        }
        @Override public void onPresence(int editors) {
            runOnUiThread(() -> {
                if (isActive()) binding.presenceText.setText(editors > 1
                        ? R.string.note_presence_together : R.string.note_presence_solo);
            });
        }
    }

    private void applyLiveVersion(String body, int revision) {
        String localBody = binding.bodyInput.getText().toString();
        boolean safeToRender = localBody.equals(serverBody) || localBody.equals(body);
        serverBody = body;
        current = withBody(body, revision);
        if (safeToRender) {
            rendering = true;
            binding.bodyInput.setText(body);
            rendering = false;
            drafts.clear(current.id);
            binding.statusText.setText(R.string.note_synced);
        } else {
            showConflict(body);
            binding.statusText.setText(R.string.note_reconcile);
        }
    }
}
