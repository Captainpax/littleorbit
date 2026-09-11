package com.littleorbit.data.repository;

import android.content.Context;
import android.content.SharedPreferences;
import com.littleorbit.data.security.SessionStore;
import dagger.hilt.android.qualifiers.ApplicationContext;
import java.util.Optional;
import javax.inject.Inject;
import javax.inject.Singleton;

/** Persists disconnected note drafts as Keystore-encrypted local payloads. */
@Singleton
public final class NoteDraftStore {
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

    /** Immutable disconnected edit and the revision it started from. */
    public record Draft(String body, int baseRevision) {}
}
