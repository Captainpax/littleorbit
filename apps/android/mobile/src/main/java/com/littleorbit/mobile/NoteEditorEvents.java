package com.littleorbit.mobile;

import com.littleorbit.data.remote.NoteSocketClient;

/** Delivers socket callbacks on the UI thread only while their original note remains open. */
final class NoteEditorEvents implements NoteSocketClient.Listener {
    private final NotesActivity activity;
    private final String noteId;
    private final long generation;
    private final Host host;

    NoteEditorEvents(NotesActivity activity, String noteId, long generation, Host host) {
        this.activity = activity;
        this.noteId = noteId;
        this.generation = generation;
        this.host = host;
    }

    @Override public void onRemoteVersion(String body, int revision) {
        dispatch(() -> host.applyRemote(body, revision));
    }

    @Override public void onSaved(String body, int revision) {
        dispatch(() -> host.applySaved(body, revision));
    }

    @Override public void onConflict(String body, int revision) {
        dispatch(() -> host.applyConflict(body, revision));
    }

    @Override public void onFailure() {
        dispatch(host::applyFailure);
    }

    @Override public void onTerminalFailure() {
        dispatch(host::applyTerminalFailure);
    }

    @Override public void onPresence(int editors) {
        dispatch(() -> host.applyPresence(editors));
    }

    private void dispatch(Runnable callback) {
        activity.runOnUiThread(() -> {
            if (host.isActive(noteId, generation)) callback.run();
        });
    }

    interface Host {
        boolean isActive(String noteId, long generation);
        void applyRemote(String body, int revision);
        void applySaved(String body, int revision);
        void applyConflict(String body, int revision);
        void applyFailure();
        void applyTerminalFailure();
        void applyPresence(int editors);
    }
}
