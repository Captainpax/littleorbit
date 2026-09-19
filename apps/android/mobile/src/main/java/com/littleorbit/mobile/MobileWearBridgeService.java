package com.littleorbit.mobile;

import com.google.android.gms.wearable.MessageEvent;
import com.google.android.gms.wearable.Wearable;
import com.google.android.gms.wearable.WearableListenerService;
import com.littleorbit.data.DisplayCacheSyncWorker;
import com.littleorbit.data.ManagedWatchStore;
import com.littleorbit.data.RelationshipDisplayIdentity;
import com.littleorbit.data.SmoochSendWorker;
import com.littleorbit.data.repository.SmoochOutbox;
import com.littleorbit.domain.WatchProtocol;
import com.littleorbit.domain.WatchActionPolicy;
import dagger.hilt.android.AndroidEntryPoint;
import java.nio.charset.StandardCharsets;
import javax.inject.Inject;
import org.json.JSONObject;

/** Revalidates every credential-free action arriving from the explicitly managed watch. */
@AndroidEntryPoint
public final class MobileWearBridgeService extends WearableListenerService {
    @Inject ManagedWatchStore watches;
    @Inject RelationshipDisplayIdentity relationships;
    @Inject SmoochOutbox smooches;

    @Override
    public void onMessageReceived(MessageEvent event) {
        String path = event.getPath();
        if (WatchProtocol.STATUS.equals(path)) acceptStatus(event);
        else if (WatchProtocol.SMOOCH.equals(path)) acceptSmooch(event);
        else if (WatchProtocol.REFRESH.equals(path)) acceptRefresh(event);
    }

    private void acceptStatus(MessageEvent event) {
        if (!watches.authorizes(event.getSourceNodeId())) return;
        try {
            JSONObject value = json(event);
            if (!targetGenerationMatches(value)) return;
            watches.recordStatus(
                    event.getSourceNodeId(), value.optString("version_name", ""),
                    value.optInt("version_code", 0), value.optInt("protocol", 0),
                    value.optInt("queued_actions", 0), value.optLong("observed_at", 0));
        } catch (Exception ignored) {
            // Malformed untrusted messages do not alter local state.
        }
    }

    private void acceptSmooch(MessageEvent event) {
        String operationId = "";
        String result = "rejected";
        try {
            JSONObject value = json(event);
            operationId = value.getString("operation_id");
            if (validSmooch(event.getSourceNodeId(), value, operationId)) {
                smooches.enqueueWatch(operationId, value.getString("emoji"),
                        value.getLong("created_at"));
                SmoochSendWorker.enqueue(this);
                result = "accepted_queued";
            }
        } catch (Exception ignored) {
            // A response without private data allows the watch to discard terminal failures.
        }
        sendResult(event.getSourceNodeId(), operationId, result);
    }

    private boolean validSmooch(String nodeId, JSONObject value, String operationId) {
        ManagedWatchStore.Snapshot watch = watches.read();
        RelationshipDisplayIdentity.Snapshot relationship = relationships.read();
        WatchActionPolicy.Request request = new WatchActionPolicy.Request(
                nodeId, value.optInt("protocol"), value.optLong("watch_generation"),
                value.optString("relationship_id"),
                value.optLong("relationship_generation"), operationId,
                value.optString("emoji"), value.optLong("created_at"));
        WatchActionPolicy.Authority authority = new WatchActionPolicy.Authority(
                watch.enabled(), watch.smoochEnabled(), watch.nodeId(), watch.generation(),
                relationship.active(), relationship.relationshipId(), relationship.generation());
        return WatchActionPolicy.authorized(request, authority, System.currentTimeMillis());
    }

    private void acceptRefresh(MessageEvent event) {
        try {
            if (watches.authorizes(event.getSourceNodeId())
                    && targetGenerationMatches(json(event))) {
                DisplayCacheSyncWorker.enqueue(this);
            }
        } catch (Exception ignored) {
            // Refresh is advisory and never widens authorization.
        }
    }

    private boolean targetGenerationMatches(JSONObject value) {
        return value.optInt("protocol") == WatchProtocol.VERSION
                && value.optLong("watch_generation") == watches.read().generation();
    }

    private void sendResult(String nodeId, String operationId, String result) {
        try {
            byte[] bytes = new JSONObject().put("protocol", WatchProtocol.VERSION)
                    .put("operation_id", operationId).put("result", result)
                    .toString().getBytes(StandardCharsets.UTF_8);
            Wearable.getMessageClient(this).sendMessage(
                    nodeId, WatchProtocol.SMOOCH_RESULT, bytes);
        } catch (Exception ignored) {
            // Stable operation IDs make a missing acknowledgement safe to retry.
        }
    }

    private static JSONObject json(MessageEvent event) throws Exception {
        return new JSONObject(new String(event.getData(), StandardCharsets.UTF_8));
    }

}
