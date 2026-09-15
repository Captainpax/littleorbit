package com.littleorbit.data.repository;

import android.content.Context;
import android.content.SharedPreferences;
import com.littleorbit.data.security.SessionStore;
import dagger.hilt.android.qualifiers.ApplicationContext;
import java.util.Optional;
import javax.inject.Inject;
import javax.inject.Singleton;
import org.json.JSONException;
import org.json.JSONObject;

/** Persists disconnected note drafts as Keystore-encrypted local payloads. */
@Singleton
public final class NoteDraftStore {
    private static final String WORKSPACE_PREFIX = "workspace:";
    private final SharedPreferences preferences;
    private final SessionStore cipher;

    /** Creates encrypted draft storage. */
    @Inject
    public NoteDraftStore(@ApplicationContext Context context, SessionStore cipher) {
        this.preferences = context.getSharedPreferences(
                "little-orbit-note-drafts", Context.MODE_PRIVATE);
        this.cipher = cipher;
    }

    /** Replaces one encrypted draft and its server base revision. */
    public void save(String noteId, String body, int baseRevision) {
        preferences.edit()
                .putString(noteId + ":body", cipher.seal(body))
                .putInt(noteId + ":revision", baseRevision)
                .apply();
    }

    /** Reads a draft or clears it when the Keystore payload is no longer valid. */
    public Optional<Draft> read(String noteId) {
        String sealed = preferences.getString(noteId + ":body", null);
        if (sealed == null) {
            return Optional.empty();
        }
        Optional<String> body = cipher.open(sealed);
        if (body.isEmpty()) {
            clear(noteId);
            return Optional.empty();
        }
        return Optional.of(new Draft(
                body.get(), preferences.getInt(noteId + ":revision", 0)));
    }

    /** Deletes a draft only after acknowledgement or explicit reconciliation. */
    public void clear(String noteId) {
        preferences.edit()
                .remove(noteId + ":body")
                .remove(noteId + ":revision")
                .apply();
    }

    /** Saves one process-restorable workspace without putting relationship content in a Bundle. */
    public void saveWorkspace(String workspaceId, Workspace workspace) {
        preferences.edit()
                .putString(WORKSPACE_PREFIX + workspaceId, cipher.seal(encode(workspace)))
                .apply();
    }

    /** Commits lifecycle restoration state before Android may stop the process. */
    public void saveWorkspaceNow(String workspaceId, Workspace workspace) {
        preferences.edit()
                .putString(WORKSPACE_PREFIX + workspaceId, cipher.seal(encode(workspace)))
                .commit();
    }

    /** Reads one encrypted workspace or removes it after corruption or key invalidation. */
    public Optional<Workspace> readWorkspace(String workspaceId) {
        String key = WORKSPACE_PREFIX + workspaceId;
        String sealed = preferences.getString(key, null);
        if (sealed == null) return Optional.empty();
        Optional<Workspace> workspace = cipher.open(sealed).flatMap(NoteDraftStore::decode);
        if (workspace.isEmpty()) preferences.edit().remove(key).apply();
        return workspace;
    }

    /** Removes one completed or deliberately abandoned workspace. */
    public void clearWorkspace(String workspaceId) {
        preferences.edit().remove(WORKSPACE_PREFIX + workspaceId).apply();
    }

    /** Commits workspace removal before leaving relationship content behind. */
    public void clearWorkspaceNow(String workspaceId) {
        preferences.edit().remove(WORKSPACE_PREFIX + workspaceId).commit();
    }

    /** Synchronously purges every relationship draft during account or couple transitions. */
    public void clearAll() {
        preferences.edit().clear().commit();
    }

    private static String encode(Workspace workspace) {
        try {
            return new JSONObject()
                    .put("version", 1)
                    .put("note_id", nullable(workspace.noteId))
                    .put("server_title", workspace.serverTitle)
                    .put("title", workspace.title)
                    .put("server_body", workspace.serverBody)
                    .put("body", workspace.body)
                    .put("base_revision", workspace.baseRevision)
                    .put("metadata_revision", workspace.metadataRevision)
                    .put("updated_at", nullable(workspace.updatedAt))
                    .put("archived_at", nullable(workspace.archivedAt))
                    .put("purge_after", nullable(workspace.purgeAfter))
                    .put("create_operation_id", nullable(workspace.createOperationId))
                    .put("selection_start", workspace.selectionStart)
                    .put("selection_end", workspace.selectionEnd)
                    .put("preview", workspace.preview)
                    .toString();
        } catch (JSONException failure) {
            throw new IllegalStateException("Note workspace could not be encoded", failure);
        }
    }

    private static Optional<Workspace> decode(String value) {
        try {
            JSONObject json = new JSONObject(value);
            if (json.optInt("version") != 1) return Optional.empty();
            return Optional.of(new Workspace(
                    optional(json, "note_id"), json.getString("server_title"),
                    json.getString("title"), json.getString("server_body"),
                    json.getString("body"), json.getInt("base_revision"),
                    json.getInt("metadata_revision"), optional(json, "updated_at"),
                    optional(json, "archived_at"), optional(json, "purge_after"),
                    optional(json, "create_operation_id"),
                    json.getInt("selection_start"), json.getInt("selection_end"),
                    json.getBoolean("preview")));
        } catch (JSONException | RuntimeException failure) {
            return Optional.empty();
        }
    }

    private static Object nullable(String value) {
        return value == null ? JSONObject.NULL : value;
    }

    private static String optional(JSONObject json, String name) {
        return json.isNull(name) ? null : json.optString(name, null);
    }

    /** Immutable disconnected edit and the revision it started from. */
    public record Draft(String body, int baseRevision) {}

    /** Encrypted UI restoration state for one open note or unsaved new document. */
    public record Workspace(
            String noteId,
            String serverTitle,
            String title,
            String serverBody,
            String body,
            int baseRevision,
            int metadataRevision,
            String updatedAt,
            String archivedAt,
            String purgeAfter,
            String createOperationId,
            int selectionStart,
            int selectionEnd,
            boolean preview) {
        /** Clamps selection endpoints to a UTF-16 body without splitting persisted content. */
        public Workspace {
            serverTitle = serverTitle == null ? "" : serverTitle;
            title = title == null ? "" : title;
            serverBody = serverBody == null ? "" : serverBody;
            body = body == null ? "" : body;
            selectionStart = Math.max(0, Math.min(selectionStart, body.length()));
            selectionEnd = Math.max(selectionStart, Math.min(selectionEnd, body.length()));
        }
    }
}
