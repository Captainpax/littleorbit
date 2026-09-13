package com.littleorbit.data.remote;

import com.littleorbit.data.BuildConfig;
import com.littleorbit.data.security.SessionStore;
import java.util.ArrayDeque;
import java.util.ArrayList;
import java.util.List;
import java.util.UUID;
import java.util.concurrent.Executors;
import java.util.concurrent.ScheduledExecutorService;
import java.util.concurrent.TimeUnit;
import javax.inject.Inject;
import javax.inject.Singleton;
import okhttp3.OkHttpClient;
import okhttp3.Request;
import okhttp3.Response;
import okhttp3.WebSocket;
import okhttp3.WebSocketListener;
import org.json.JSONException;
import org.json.JSONObject;

/** One persistent authenticated WSS session for deterministic code-point note edits. */
@Singleton
public final class NoteSocketClient {
    private final OkHttpClient client;
    private final SessionStore sessions;
    private final ScheduledExecutorService reconnects =
            Executors.newSingleThreadScheduledExecutor(runnable -> {
                Thread thread = new Thread(runnable, "note-wss-reconnect");
                thread.setDaemon(true);
                return thread;
            });

    /** Creates a socket boundary that sends tokens only in an authorization header. */
    @Inject
    public NoteSocketClient(OkHttpClient client, SessionStore sessions) {
        this.client = client;
        this.sessions = sessions;
    }

    /** Opens one editor connection that owns observation, edits, acknowledgements, and retry. */
    public EditorConnection openEditor(
            String noteId, String serverBody, int revision, Listener listener) {
        String token = sessions.read().orElse(null);
        if (token == null) {
            listener.onFailure();
            return EditorConnection.closed();
        }
        EditorSession session = new EditorSession(
                noteId, token, serverBody, revision, listener);
        session.open();
        return session;
    }

    private static Request.Builder versionedRequest() {
        return new Request.Builder()
                .header("X-Little-Orbit-Client", "android")
                .header("X-Little-Orbit-Version", BuildConfig.CLIENT_VERSION_NAME)
                .header(
                        "X-Little-Orbit-Version-Code",
                        Integer.toString(BuildConfig.CLIENT_VERSION_CODE));
    }

    static List<Operation> editPlan(String oldBody, String newBody) {
        int[] oldPoints = oldBody.codePoints().toArray();
        int[] newPoints = newBody.codePoints().toArray();
        int prefix = commonPrefix(oldPoints, newPoints);
        int suffix = commonSuffix(oldPoints, newPoints, prefix);
        List<Operation> result = new ArrayList<>(2);
        int deleteLength = oldPoints.length - prefix - suffix;
        if (deleteLength > 0) result.add(Operation.delete(prefix, deleteLength));
        int insertLength = newPoints.length - prefix - suffix;
        if (insertLength > 0) {
            result.add(Operation.insert(
                    prefix, new String(newPoints, prefix, insertLength)));
        }
        return result;
    }

    private static int commonPrefix(int[] first, int[] second) {
        int prefix = 0;
        while (prefix < first.length
                && prefix < second.length
                && first[prefix] == second[prefix]) {
            prefix++;
        }
        return prefix;
    }

    private static int commonSuffix(int[] first, int[] second, int prefix) {
        int suffix = 0;
        while (suffix < first.length - prefix
                && suffix < second.length - prefix
                && first[first.length - suffix - 1] == second[second.length - suffix - 1]) {
            suffix++;
        }
        return suffix;
    }

    /** UI callbacks that keep remote updates and explicit conflicts distinct. */
    public interface Listener {
        /** Reports a partner or reconnect snapshot without discarding a local draft. */
        void onRemoteVersion(String serverBody, int revision);

        /** Reports that every operation for the latest submitted body was acknowledged. */
        void onSaved(String serverBody, int revision);

        /** Requires an explicit choice between local and current server content. */
        void onConflict(String serverBody, int revision);

        /** Reports transport, authorization, or malformed-response failure. */
        void onFailure();

        /** Reports transient connected editor count without exposing identity. */
        default void onPresence(int editors) {}
    }

    /** Mutable connection handle owned by one editor screen. */
    public interface EditorConnection {
        /** Submits the latest desired body; intermediate keystrokes are coalesced. */
        void update(String body);

        /** Resumes after conflict using the retained local body. */
        void keepLocal(String body);

        /** Accepts the latest server body and clears pending operations. */
        void acceptServer();

        /** Closes the session without deleting the encrypted draft. */
        void close();

        /** Returns an inert handle for signed-out callers. */
        static EditorConnection closed() {
            return new EditorConnection() {
                @Override public void update(String body) {}
                @Override public void keepLocal(String body) {}
                @Override public void acceptServer() {}
                @Override public void close() {}
            };
        }
    }

    record Operation(String id, String kind, int position, String text, int length) {
        static Operation insert(int position, String text) {
            return new Operation(UUID.randomUUID().toString(), "insert", position, text, 0);
        }

        static Operation delete(int position, int length) {
            return new Operation(UUID.randomUUID().toString(), "delete", position, "", length);
        }
    }

    private final class EditorSession extends WebSocketListener implements EditorConnection {
        private final String noteId;
        private final String token;
        private final Listener listener;
        private final ArrayDeque<Operation> pending = new ArrayDeque<>();
        private WebSocket socket;
        private String serverBody;
        private String desiredBody;
        private int revision;
        private boolean ready;
        private boolean paused;
        private boolean closed;
        private boolean reconnectScheduled;

        EditorSession(
                String noteId, String token, String body, int revision, Listener listener) {
            this.noteId = noteId;
            this.token = token;
            this.serverBody = body;
            this.desiredBody = body;
            this.revision = revision;
            this.listener = listener;
        }

        synchronized void open() {
            if (closed) return;
            Request request = versionedRequest()
                    .url(BuildConfig.WS_BASE_URL + "ws/v1/notes/" + noteId)
                    .header("Authorization", "Bearer " + token)
                    .build();
            socket = client.newWebSocket(request, this);
        }

        @Override
        public synchronized void onOpen(WebSocket webSocket, Response response) {
            socket = webSocket;
            reconnectScheduled = false;
        }

        @Override
        public synchronized void onMessage(WebSocket webSocket, String text) {
            try {
                handle(new JSONObject(text));
            } catch (JSONException exception) {
                listener.onFailure();
                webSocket.close(1002, "invalid server message");
            }
        }

        private void handle(JSONObject message) throws JSONException {
            String type = message.optString("type");
            if ("note.snapshot".equals(type)) {
                handleSnapshot(message);
            } else if ("note.ack".equals(type)) {
                handleAck(message);
            } else if ("note.conflict".equals(type)) {
                handleConflict(message);
            } else if ("note.presence".equals(type)) {
                listener.onPresence(message.optInt("editors"));
            } else if ("note.error".equals(type)) {
                listener.onFailure();
            }
        }

        private void handleSnapshot(JSONObject message) throws JSONException {
            serverBody = message.optString("body");
            revision = message.getInt("revision");
            ready = true;
            if (pending.isEmpty()) {
                listener.onRemoteVersion(serverBody, revision);
                drain();
            } else {
                sendCurrent();
            }
        }

        private void handleAck(JSONObject message) throws JSONException {
            String operationId = message.optString("operation_id");
            Operation current = pending.peekFirst();
            serverBody = message.optString("body");
            revision = message.getInt("revision");
            if (current == null || !current.id().equals(operationId)) {
                if (pending.isEmpty()) listener.onRemoteVersion(serverBody, revision);
                return;
            }
            if (message.optBoolean("duplicate")) pending.clear();
            else pending.removeFirst();
            if (pending.isEmpty()) {
                listener.onSaved(serverBody, revision);
                drain();
            } else {
                sendCurrent();
            }
        }

        private void handleConflict(JSONObject message) throws JSONException {
            pending.clear();
            serverBody = message.optString("body");
            revision = message.getInt("revision");
            paused = true;
            listener.onConflict(serverBody, revision);
        }

        @Override
        public synchronized void update(String body) {
            desiredBody = body;
            drain();
        }

        @Override
        public synchronized void keepLocal(String body) {
            desiredBody = body;
            paused = false;
            drain();
        }

        @Override
        public synchronized void acceptServer() {
            desiredBody = serverBody;
            pending.clear();
            paused = false;
        }

        private void drain() {
            if (!ready || paused || !pending.isEmpty() || desiredBody.equals(serverBody)) return;
            pending.addAll(editPlan(serverBody, desiredBody));
            sendCurrent();
        }

        private void sendCurrent() {
            Operation operation = pending.peekFirst();
            if (operation == null || socket == null) return;
            try {
                JSONObject message = new JSONObject()
                        .put("operation_id", operation.id())
                        .put("base_revision", revision)
                        .put("kind", operation.kind())
                        .put("position", operation.position());
                if ("insert".equals(operation.kind())) message.put("text", operation.text());
                else message.put("length", operation.length());
                if (!socket.send(message.toString())) scheduleReconnect();
            } catch (JSONException exception) {
                listener.onFailure();
            }
        }

        @Override
        public synchronized void onFailure(
                WebSocket webSocket, Throwable failure, Response response) {
            if (closed) return;
            ready = false;
            listener.onFailure();
            scheduleReconnect();
        }

        @Override
        public synchronized void onClosed(WebSocket webSocket, int code, String reason) {
            if (!closed) scheduleReconnect();
        }

        private void scheduleReconnect() {
            if (closed || reconnectScheduled) return;
            reconnectScheduled = true;
            reconnects.schedule(() -> {
                synchronized (EditorSession.this) {
                    reconnectScheduled = false;
                    open();
                }
            }, 2, TimeUnit.SECONDS);
        }

        @Override
        public synchronized void close() {
            closed = true;
            ready = false;
            if (socket != null) socket.close(1000, "editor closed");
        }
    }
}
