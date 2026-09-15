package com.littleorbit.mobile;

import com.littleorbit.data.remote.NoteApiModels;
import com.littleorbit.data.repository.OrbitRepository;
import com.littleorbit.mobile.databinding.ActivityNotesBinding;
import java.util.UUID;
import java.util.function.Consumer;

/** Keeps one retry identity and one in-flight request for a new shared document. */
final class NoteCreationCoordinator {
    private String operationId;
    private boolean inFlight;

    void begin() {
        operationId = UUID.randomUUID().toString();
        inFlight = false;
    }

    void restore(String savedOperationId) {
        operationId = savedOperationId;
        inFlight = false;
    }

    void clear() {
        operationId = null;
        inFlight = false;
    }

    String operationId() {
        return operationId;
    }

    void submit(
            NotesActivity activity,
            OrbitRepository orbit,
            ActivityNotesBinding binding,
            String title,
            String body,
            Consumer<NoteApiModels.Note> success) {
        if (inFlight) return;
        if (operationId == null) begin();
        inFlight = true;
        binding.syncButton.setEnabled(false);
        NoteApiModels.CreateRequest request =
                new NoteApiModels.CreateRequest(operationId, title, body);
        AsyncUi.observe(activity, orbit.createNote(request), binding.statusText, () -> {
            inFlight = false;
            binding.syncButton.setEnabled(true);
        }, success);
    }
}
