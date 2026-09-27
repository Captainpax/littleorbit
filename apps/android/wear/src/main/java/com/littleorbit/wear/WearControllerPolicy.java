package com.littleorbit.wear;

/** Pure controller-node and target-generation authorization rules. */
final class WearControllerPolicy {
    private WearControllerPolicy() {}

    static Decision decide(
            Authority current,
            String localNodeId,
            String targetNodeId,
            long generation,
            String sourceNodeId) {
        if (generation <= 0 || generation < current.generation()
                || blank(sourceNodeId)) return Decision.reject(current);
        if (!localNodeId.equals(targetNodeId)) {
            if (generation > current.generation()) {
                return new Decision(false, true, new Authority("", generation, ""));
            }
            return Decision.reject(current);
        }
        boolean changed = generation > current.generation()
                || !targetNodeId.equals(current.targetNodeId());
        String controller = changed || blank(current.controllerNodeId())
                ? sourceNodeId : current.controllerNodeId();
        if (!sourceNodeId.equals(controller)) return Decision.reject(current);
        return new Decision(true, changed,
                new Authority(targetNodeId, generation, controller));
    }

    private static boolean blank(String value) {
        return value == null || value.isBlank();
    }

    record Authority(String targetNodeId, long generation, String controllerNodeId) {}

    record Decision(boolean accepted, boolean clearPrivateState, Authority next) {
        static Decision reject(Authority current) {
            return new Decision(false, false, current);
        }
    }
}
