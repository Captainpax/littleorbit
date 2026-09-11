package com.littleorbit.data.remote;

import com.littleorbit.data.security.SessionStore;
import java.util.ArrayList;
import java.util.List;
import java.util.UUID;
import javax.inject.Inject;
import javax.inject.Singleton;
import okhttp3.OkHttpClient;
import okhttp3.Request;
import okhttp3.Response;
import okhttp3.WebSocket;
import okhttp3.WebSocketListener;
import org.json.JSONException;
import org.json.JSONObject;

/** Authenticated WSS client for deterministic code-point note operations. */
@Singleton
public final class NoteSocketClient {
    private final OkHttpClient client;
    private final SessionStore sessions;

    /** Creates a socket boundary that sends tokens only in an authorization header. */
    @Inject
    public NoteSocketClient(OkHttpClient client, SessionStore sessions) {
        this.client = client;
        this.sessions = sessions;
    }

    /** Replaces a local draft through one or two operational-transform edits. */
    public Connection replace(
            String noteId,
            int baseRevision,
            String oldBody,
            String newBody,
            Listener listener) {
        List<Operation> operations = editPlan(oldBody, newBody);
        if (operations.isEmpty()) {
            listener.onSynced(oldBody, baseRevision);
            return () -> {};
        }
        String token = sessions.read().orElse(null);
        if (token == null) {
            listener.onFailure();
            return () -> {};
        }
        Request request = new Request.Builder()
                .url("wss://lil-orb.pax-kun.com/ws/v1/notes/" + noteId)
                .header("Authorization", "Bearer " + token)
                .build();
        SyncListener socketListener = new SyncListener(
                operations, baseRevision, listener);
        WebSocket socket = client.newWebSocket(request, socketListener);
        socketListener.attach(socket);
        return () -> socket.close(1000, "screen closed");
    }

    /** Keeps a note subscribed so the partner's acknowledged edits arrive live. */
    public Connection observe(String noteId, Listener listener) {
        String token = sessions.read().orElse(null);
        if (token == null) {
            listener.onFailure();
            return () -> {};
        }
        Request request = new Request.Builder()
                .url("wss://lil-orb.pax-kun.com/ws/v1/notes/" + noteId)
                .header("Authorization", "Bearer " + token)
                .build();
        WebSocket socket = client.newWebSocket(request, new ObserveListener(listener));
        return () -> socket.close(1000, "screen closed");
    }

    private static List<Operation> editPlan(String oldBody, String newBody) {
        int[] oldPoints = oldBody.codePoints().toArray();
        int[] newPoints = newBody.codePoints().toArray();
        int prefix = 0;
        while (prefix < oldPoints.length
                && prefix < newPoints.length
                && oldPoints[prefix] == newPoints[prefix]) {
            prefix++;
        }
        int suffix = 0;
        while (suffix < oldPoints.length - prefix
                && suffix < newPoints.length - prefix
                && oldPoints[oldPoints.length - suffix - 1]
                        == newPoints[newPoints.length - suffix - 1]) {
            suffix++;
        }
        List<Operation> result = new ArrayList<>(2);
        int deleteLength = oldPoints.length - prefix - suffix;
        if (deleteLength > 0) {
            result.add(Operation.delete(prefix, deleteLength));
        }
        int insertLength = newPoints.length - prefix - suffix;
        if (insertLength > 0) {
            result.add(Operation.insert(
                    prefix, new String(newPoints, prefix, insertLength)));
        }
        return result;
    }

    /** Callbacks that keep conflicts explicit rather than overwriting either version. */
    public interface Listener {
        /** Called after every operation is acknowledged. */
        void onSynced(String serverBody, int revision);

        /** Called with both the retained local draft and current server version available. */
        void onConflict(String serverBody, int revision);

        /** Called for transport, authorization, or malformed-response failure. */
        void onFailure();
    }

    /** Close handle owned by an activity or view model. */
    public interface Connection {
        /** Closes the active socket without deleting a draft. */
        void close();
    }

    private record Operation(String kind, int position, String text, int length) {
        static Operation insert(int position, String text) {
            return new Operation("insert", position, text, 0);
        }

        static Operation delete(int position, int length) {
            return new Operation("delete", position, "", length);
        }
    }

    private static final class SyncListener extends WebSocketListener {
        private final List<Operation> operations;
        private final Listener listener;
        private WebSocket socket;
        private int revision;
        private int index;
        private String currentOperationId;

        SyncListener(List<Operation> operations, int revision, Listener listener) {
            this.operations = operations;
            this.revision = revision;
            this.listener = listener;
        }

        void attach(WebSocket socket) {
            this.socket = socket;
        }

        @Override
        public void onOpen(WebSocket webSocket, Response response) {
            socket = webSocket;
            sendNext();
        }

        @Override
        public void onMessage(WebSocket webSocket, String text) {
            try {
                JSONObject message = new JSONObject(text);
                if ("note.conflict".equals(message.optString("type"))) {
                    listener.onConflict(
                            message.optString("body"), message.optInt("revision"));
                    webSocket.close(1000, "explicit reconciliation required");
                    return;
                }
                if (!"note.ack".equals(message.optString("type"))
                        || !currentOperationId.equals(message.optString("operation_id"))) {
                    return;
                }
                revision = message.getInt("revision");
                index++;
                if (index < operations.size()) {
                    sendNext();
                } else {
                    listener.onSynced(message.optString("body"), revision);
                    webSocket.close(1000, "sync complete");
                }
            } catch (JSONException exception) {
                listener.onFailure();
                webSocket.close(1002, "invalid server message");
            }
        }

        @Override
        public void onFailure(WebSocket webSocket, Throwable failure, Response response) {
            listener.onFailure();
        }

        private void sendNext() {
            Operation operation = operations.get(index);
            currentOperationId = UUID.randomUUID().toString();
            try {
                JSONObject message = new JSONObject()
                        .put("operation_id", currentOperationId)
                        .put("base_revision", revision)
                        .put("kind", operation.kind)
                        .put("position", operation.position);
                if ("insert".equals(operation.kind)) {
                    message.put("text", operation.text);
                } else {
                    message.put("length", operation.length);
                }
                socket.send(message.toString());
            } catch (JSONException exception) {
                listener.onFailure();
            }
        }
    }

    private static final class ObserveListener extends WebSocketListener {
        private final Listener listener;

        ObserveListener(Listener listener) {
            this.listener = listener;
        }

        @Override
        public void onMessage(WebSocket webSocket, String text) {
            try {
                JSONObject message = new JSONObject(text);
                String type = message.optString("type");
                if ("note.snapshot".equals(type) || "note.ack".equals(type)) {
                    listener.onSynced(message.optString("body"), message.getInt("revision"));
                } else if ("note.conflict".equals(type)) {
                    listener.onConflict(message.optString("body"), message.getInt("revision"));
                }
            } catch (JSONException exception) {
                listener.onFailure();
                webSocket.close(1002, "invalid server message");
            }
        }

        @Override
        public void onFailure(WebSocket webSocket, Throwable failure, Response response) {
            listener.onFailure();
        }
    }
}
