package com.littleorbit.wear;

import android.content.Context;
import android.content.SharedPreferences;

/** Rejects records for other watches and preserves a monotonic target purge barrier. */
final class WearTargetGuard {
    private static final String PREFERENCES = "little_orbit_watch_target_v1";

    private WearTargetGuard() {}

    static synchronized boolean accept(
            Context context,
            String localNodeId,
            String targetNodeId,
            long generation,
            String sourceNodeId) {
        State current = read(context);
        WearControllerPolicy.Decision decision = WearControllerPolicy.decide(
                new WearControllerPolicy.Authority(
                        current.targetNodeId(), current.generation(), current.controllerNodeId()),
                localNodeId, targetNodeId, generation, sourceNodeId);
        if (decision.clearPrivateState()) clearPrivateState(context);
        WearControllerPolicy.Authority next = decision.next();
        if (decision.accepted() || decision.clearPrivateState()) {
            persist(context, new State(
                    next.targetNodeId(), next.generation(), next.controllerNodeId()));
        }
        return decision.accepted();
    }

    static synchronized boolean purge(Context context, long generation) {
        State current = read(context);
        if (generation <= 0 || generation < current.generation()) return false;
        purgeAndPersist(context, generation, "");
        return true;
    }

    static synchronized boolean isCurrent(Context context, String targetNodeId, long generation) {
        State current = read(context);
        return current.generation() == generation
                && current.targetNodeId().equals(targetNodeId);
    }

    static synchronized long generation(Context context) {
        return read(context).generation();
    }

    static synchronized String controllerNodeId(Context context) {
        return read(context).controllerNodeId();
    }

    static synchronized boolean authorizesController(Context context, String nodeId) {
        String controller = read(context).controllerNodeId();
        return !controller.isBlank() && controller.equals(nodeId);
    }

    static synchronized boolean authorizesRelationshipSource(Context context, String nodeId) {
        String controller = read(context).controllerNodeId();
        return controller.isBlank() || controller.equals(nodeId);
    }

    static synchronized void clearController(Context context) {
        State current = read(context);
        persist(context, new State(current.targetNodeId(), current.generation(), ""));
    }

    static synchronized boolean authorizesManagedPurge(
            Context context,
            String localNodeId,
            String targetNodeId,
            long generation,
            String sourceNodeId) {
        State current = read(context);
        if (generation <= 0 || generation < current.generation()
                || !localNodeId.equals(targetNodeId)
                || sourceNodeId == null || sourceNodeId.isBlank()) return false;
        return current.controllerNodeId().isBlank()
                || current.controllerNodeId().equals(sourceNodeId);
    }

    private static void purgeAndPersist(Context context, long generation, String target) {
        clearPrivateState(context);
        persist(context, new State(target, generation, ""));
    }

    private static void clearPrivateState(Context context) {
        WearDisplayCache.clearValues(context);
        WearProfileStore.clearAll(context);
        WearConfiguration.clear(context);
        WearSmoochQueue.clear(context);
    }

    private static State read(Context context) {
        SharedPreferences values = context.getSharedPreferences(PREFERENCES, Context.MODE_PRIVATE);
        return new State(
                values.getString("target_node_id", ""),
                values.getLong("watch_generation", 0),
                values.getString("controller_node_id", ""));
    }

    private static void persist(Context context, State state) {
        boolean stored = context.getSharedPreferences(PREFERENCES, Context.MODE_PRIVATE).edit()
                .putString("target_node_id", state.targetNodeId())
                .putLong("watch_generation", state.generation())
                .putString("controller_node_id", state.controllerNodeId()).commit();
        if (!stored) clearPrivateState(context);
    }

    private record State(String targetNodeId, long generation, String controllerNodeId) {}
}
