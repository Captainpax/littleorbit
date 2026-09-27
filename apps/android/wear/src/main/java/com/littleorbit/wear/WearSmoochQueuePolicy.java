package com.littleorbit.wear;

import java.util.ArrayList;
import java.util.List;

/** Pure queue rules kept separate from encrypted Android storage. */
final class WearSmoochQueuePolicy {
    static final int MAX_ITEMS = 5;
    static final long LIFETIME_MILLIS = 15L * 60 * 1_000;

    private WearSmoochQueuePolicy() {}

    static List<WearSmoochQueue.Pending> current(
            List<WearSmoochQueue.Pending> values, long now) {
        List<WearSmoochQueue.Pending> current = new ArrayList<>();
        for (WearSmoochQueue.Pending item : values) {
            long createdAt = item.createdAt();
            if (createdAt > 0 && createdAt <= now
                    && createdAt > now - LIFETIME_MILLIS) {
                current.add(item);
            }
        }
        return current;
    }

    static List<WearSmoochQueue.Pending> enqueue(
            List<WearSmoochQueue.Pending> values,
            WearSmoochQueue.Pending item,
            long now) {
        List<WearSmoochQueue.Pending> updated = current(values, now);
        if (current(List.of(item), now).isEmpty()) return updated;
        if (updated.stream().noneMatch(value -> value.operationId().equals(item.operationId()))) {
            updated.add(item);
        }
        while (updated.size() > MAX_ITEMS) updated.remove(0);
        return updated;
    }
}
