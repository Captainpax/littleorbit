package com.littleorbit.mobile;

import android.os.Bundle;
import android.view.View;
import androidx.appcompat.app.AppCompatActivity;
import com.littleorbit.data.remote.ApiModels;
import com.littleorbit.data.remote.NoteSocketClient;
import com.littleorbit.data.repository.NoteDraftStore;
import com.littleorbit.data.repository.OrbitRepository;
import com.littleorbit.mobile.databinding.ActivityNotesBinding;
import dagger.hilt.android.AndroidEntryPoint;
import java.util.List;
import java.util.UUID;
import javax.inject.Inject;

/** Shared note editor with encrypted drafts and explicit stale-version reconciliation. */
@AndroidEntryPoint
public final class NotesActivity extends InsetAwareActivity {
    @Inject OrbitRepository orbit;
    @Inject NoteDraftStore drafts;
    @Inject NoteSocketClient sockets;
    private ActivityNotesBinding binding;
    private ApiModels.Note current;
    private String serverBody = "";
    private NoteSocketClient.Connection syncConnection = () -> {};
    private NoteSocketClient.Connection liveConnection = () -> {};

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        binding = ActivityNotesBinding.inflate(getLayoutInflater());
        setContentView(binding.getRoot());
        binding.createButton.setOnClickListener(view -> create());
        binding.syncButton.setOnClickListener(view -> sync());
        binding.useServerButton.setOnClickListener(view -> useServerVersion());
        load();
    }

    private void load() {
        AsyncUi.observe(this, orbit.notes(), binding.statusText, this::showNotes);
    }

    private void showNotes(List<ApiModels.Note> notes) {
        if (notes.isEmpty()) {
            binding.statusText.setText(R.string.no_notes);
            return;
        }
        current = notes.get(0);
        serverBody = current.body;
        binding.titleInput.setText(current.title);
        NoteDraftStore.Draft draft = drafts.read(current.id).orElse(null);
        binding.bodyInput.setText(draft == null ? current.body : draft.body());
        boolean conflict = draft != null && draft.baseRevision() != current.revision;
        binding.serverVersionText.setText(conflict ? current.body : "");
        binding.serverVersionText.setVisibility(conflict ? View.VISIBLE : View.GONE);
        binding.useServerButton.setVisibility(conflict ? View.VISIBLE : View.GONE);
        binding.statusText.setText(conflict
                ? R.string.note_reconcile
                : R.string.note_ready);
        liveConnection.close();
        liveConnection = sockets.observe(current.id, new LiveResult());
    }

    private void create() {
        String title = binding.titleInput.getText().toString().trim();
        String body = binding.bodyInput.getText().toString();
        if (title.isEmpty()) {
            binding.statusText.setText(R.string.complete_required_fields);
            return;
        }
        ApiModels.NoteCreateRequest request = new ApiModels.NoteCreateRequest(
                UUID.randomUUID().toString(), title, body);
        AsyncUi.observe(this, orbit.createNote(request), binding.statusText, note -> {
            current = note;
            serverBody = note.body;
            drafts.clear(note.id);
            binding.statusText.setText(R.string.note_ready);
            liveConnection.close();
            liveConnection = sockets.observe(note.id, new LiveResult());
        });
    }

    private void sync() {
        if (current == null) {
            create();
            return;
        }
        String localBody = binding.bodyInput.getText().toString();
        drafts.save(current.id, localBody, current.revision);
        syncConnection.close();
        syncConnection = sockets.replace(
                current.id,
                current.revision,
                serverBody,
                localBody,
                new SocketResult());
        binding.statusText.setText(R.string.syncing_note);
    }

    private void useServerVersion() {
        if (current == null) {
            return;
        }
        binding.bodyInput.setText(serverBody);
        drafts.clear(current.id);
        binding.serverVersionText.setVisibility(View.GONE);
        binding.useServerButton.setVisibility(View.GONE);
        binding.statusText.setText(R.string.note_ready);
    }

    @Override
    protected void onPause() {
        super.onPause();
        if (current != null
                && !binding.bodyInput.getText().toString().equals(serverBody)) {
            drafts.save(
                    current.id,
                    binding.bodyInput.getText().toString(),
                    current.revision);
        }
    }

    @Override
    protected void onDestroy() {
        syncConnection.close();
        liveConnection.close();
        super.onDestroy();
    }

    private final class SocketResult implements NoteSocketClient.Listener {
        @Override
        public void onSynced(String body, int revision) {
            runOnUiThread(() -> {
                serverBody = body;
                current = new ApiModels.Note(
                        current.id, current.title, body, revision, current.updatedAt);
                drafts.clear(current.id);
                binding.statusText.setText(R.string.note_synced);
            });
        }

        @Override
        public void onConflict(String body, int revision) {
            runOnUiThread(() -> {
                serverBody = body;
                current = new ApiModels.Note(
                        current.id, current.title, body, revision, current.updatedAt);
                binding.serverVersionText.setText(body);
                binding.serverVersionText.setVisibility(View.VISIBLE);
                binding.useServerButton.setVisibility(View.VISIBLE);
                binding.statusText.setText(R.string.note_reconcile);
            });
        }

        @Override
        public void onFailure() {
            runOnUiThread(() -> binding.statusText.setText(R.string.note_draft_preserved));
        }
    }

    private final class LiveResult implements NoteSocketClient.Listener {
        @Override
        public void onSynced(String body, int revision) {
            runOnUiThread(() -> applyLiveVersion(body, revision));
        }

        @Override
        public void onConflict(String body, int revision) {
            runOnUiThread(() -> showLiveConflict(body, revision));
        }

        @Override
        public void onFailure() {
            runOnUiThread(() -> binding.statusText.setText(R.string.note_draft_preserved));
        }
    }

    private void applyLiveVersion(String body, int revision) {
        String localBody = binding.bodyInput.getText().toString();
        boolean unchangedLocally = localBody.equals(serverBody);
        boolean matchesAcknowledgedBody = localBody.equals(body);
        serverBody = body;
        current = new ApiModels.Note(
                current.id, current.title, body, revision, current.updatedAt);
        if (unchangedLocally || matchesAcknowledgedBody) {
            binding.bodyInput.setText(body);
            drafts.clear(current.id);
            binding.statusText.setText(R.string.note_synced);
        } else {
            showLiveConflict(body, revision);
        }
    }

    private void showLiveConflict(String body, int revision) {
        serverBody = body;
        current = new ApiModels.Note(
                current.id, current.title, body, revision, current.updatedAt);
        binding.serverVersionText.setText(body);
        binding.serverVersionText.setVisibility(View.VISIBLE);
        binding.useServerButton.setVisibility(View.VISIBLE);
        binding.statusText.setText(R.string.note_reconcile);
    }
}
