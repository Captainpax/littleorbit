package com.littleorbit.wear;

import android.content.Context;
import android.content.SharedPreferences;

/** Rejects records for other watches and preserves a monotonic target purge barrier. */
final class WearTargetGuard {
    private static final String PREFERENCES = "little_orbit_watch_target_v1";

    private WearTargetGuard() {}

    static synchronized boolean accept(
            Context context, String localNodeId, String targetNodeId, long generation) {
        State current = read(context);
        if (generation <= 0 || generation < current.generation()) return false;
        if (!localNodeId.equals(targetNodeId)) {
            if (generation > current.generation()) purgeAndPersist(context, generation, "");
            return false;
        }
        boolean changed = generation > current.generation()
                || !targetNodeId.equals(current.targetNodeId());
        if (changed) clearPrivateState(context);
        persist(context, new State(targetNodeId, generation));
        return true;
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

    private static void purgeAndPersist(Context context, long generation, String target) {
        clearPrivateState(context);
        persist(context, new State(target, generation));
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
                values.getLong("watch_generation", 0));
    }

    private static void persist(Context context, State state) {
        boolean stored = context.getSharedPreferences(PREFERENCES, Context.MODE_PRIVATE).edit()
                .putString("target_node_id", state.targetNodeId())
                .putLong("watch_generation", state.generation()).commit();
        if (!stored) clearPrivateState(context);
    }

    private record State(String targetNodeId, long generation) {}
}
