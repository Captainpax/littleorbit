package com.littleorbit.mobile;

import android.os.Bundle;
import com.littleorbit.data.repository.NoteDraftStore;
import java.util.Optional;
import java.util.UUID;

/** Keeps process-restoration content in encrypted storage and only an opaque key in Bundles. */
final class NoteWorkspaceController {
    private static final String STATE_WORKSPACE_ID = "encrypted-note-workspace-id";
    private final NoteDraftStore drafts;
    private String workspaceId;
    private NoteDraftStore.Workspace restored;
    private boolean active;

    NoteWorkspaceController(NoteDraftStore drafts, Bundle savedState) {
        this.drafts = drafts;
        if (savedState == null) return;
        workspaceId = savedState.getString(STATE_WORKSPACE_ID);
        if (workspaceId == null) return;
        restored = drafts.readWorkspace(workspaceId).orElse(null);
        active = restored != null;
    }

    Optional<NoteDraftStore.Workspace> restored() {
        return Optional.ofNullable(restored);
    }

    void begin() {
        finish();
        workspaceId = UUID.randomUUID().toString();
        active = true;
    }

    void persist(NoteDraftStore.Workspace workspace) {
        if (!active) begin();
        drafts.saveWorkspace(workspaceId, workspace);
    }

    void persistNow(NoteDraftStore.Workspace workspace) {
        if (!active) begin();
        drafts.saveWorkspaceNow(workspaceId, workspace);
    }

    void saveReference(Bundle state) {
        if (active && workspaceId != null) state.putString(STATE_WORKSPACE_ID, workspaceId);
    }

    void consumeRestore() {
        restored = null;
    }

    void finish() {
        if (workspaceId != null) drafts.clearWorkspaceNow(workspaceId);
        workspaceId = null;
        restored = null;
        active = false;
    }
}
