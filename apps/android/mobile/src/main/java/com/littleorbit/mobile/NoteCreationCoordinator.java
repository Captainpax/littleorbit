package com.littleorbit.mobile;

import android.widget.TextView;
import com.littleorbit.data.remote.NoteApiModels;
import com.littleorbit.data.repository.OrbitRepository;
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

    boolean inFlight() {
        return inFlight;
    }

    void submit(
            NotesActivity activity,
            OrbitRepository orbit,
            TextView status,
            String title,
            String body,
            Runnable finished,
            Consumer<NoteApiModels.Note> success) {
        if (inFlight) return;
        if (operationId == null) begin();
        inFlight = true;
        NoteApiModels.CreateRequest request =
                new NoteApiModels.CreateRequest(operationId, title, body);
        AsyncUi.observe(activity, orbit.createNote(request), status, () -> {
            inFlight = false;
            finished.run();
        }, success);
    }
}
