package com.littleorbit.wear;

import android.content.Context;
import com.google.android.gms.wearable.MessageEvent;
import com.google.android.gms.wearable.Node;
import com.google.android.gms.wearable.Wearable;
import com.google.android.gms.wearable.WearableListenerService;
import com.littleorbit.domain.WatchProtocol;
import java.nio.charset.StandardCharsets;
import java.util.List;
import org.json.JSONObject;

/** Sends content-minimal status and short-lived actions to an authorizing phone. */
public final class WearActionService extends WearableListenerService {
    @Override
    public void onMessageReceived(MessageEvent event) {
        if (WatchProtocol.STATUS_REQUEST.equals(event.getPath())) {
            sendStatus(this, event.getSourceNodeId());
            flushToNode(this, event.getSourceNodeId());
        } else if (WatchProtocol.SMOOCH_RESULT.equals(event.getPath())) {
            acceptResult(this, event);
        }
    }

    @Override
    public void onPeerConnected(Node peer) {
        sendStatus(this, peer.getId());
        flushToNode(this, peer.getId());
    }

    static void flush(Context context) {
        Wearable.getNodeClient(context).getConnectedNodes().addOnSuccessListener(nodes -> {
            for (Node node : nodes) flushToNode(context, node.getId());
        });
    }

    static void sendStatus(Context context, String nodeId) {
        try {
            JSONObject status = new JSONObject()
                    .put("protocol", WatchProtocol.VERSION)
                    .put("watch_generation", WearTargetGuard.generation(context))
                    .put("version_name", BuildConfig.VERSION_NAME)
                    .put("version_code", BuildConfig.VERSION_CODE)
                    .put("queued_actions", WearSmoochQueue.count(context))
                    .put("observed_at", System.currentTimeMillis());
            send(context, nodeId, WatchProtocol.STATUS, status);
        } catch (Exception ignored) {
            // Status is best effort and contains no account or relationship content.
        }
    }

    private static void flushToNode(Context context, String nodeId) {
        List<WearSmoochQueue.Pending> pending =
                WearSmoochQueue.pending(context, System.currentTimeMillis());
        for (WearSmoochQueue.Pending item : pending) {
            try {
                JSONObject value = new JSONObject()
                        .put("protocol", WatchProtocol.VERSION)
                        .put("operation_id", item.operationId())
                        .put("emoji", item.emoji())
                        .put("created_at", item.createdAt())
                        .put("relationship_id", item.relationshipId())
                        .put("relationship_generation", item.relationshipGeneration())
                        .put("watch_generation", item.watchGeneration());
                send(context, nodeId, WatchProtocol.SMOOCH, value);
            } catch (Exception ignored) {
                // The encrypted queue owns the action until acknowledgement or expiry.
            }
        }
        sendStatus(context, nodeId);
    }

    private static void acceptResult(Context context, MessageEvent event) {
        try {
            JSONObject value = new JSONObject(
                    new String(event.getData(), StandardCharsets.UTF_8));
            if (value.optInt("protocol") != WatchProtocol.VERSION) return;
            String result = value.optString("result");
            if ("accepted_queued".equals(result) || "rejected".equals(result)) {
                WearSmoochQueue.remove(context, value.optString("operation_id"));
                sendStatus(context, event.getSourceNodeId());
            }
        } catch (Exception ignored) {
            // Malformed acknowledgements never gain queue authority.
        }
    }

    private static void send(Context context, String nodeId, String path, JSONObject value) {
        Wearable.getMessageClient(context).sendMessage(
                nodeId, path, value.toString().getBytes(StandardCharsets.UTF_8));
    }
}
