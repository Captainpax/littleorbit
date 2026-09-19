package com.littleorbit.wear;

import static org.junit.Assert.assertEquals;

import java.util.ArrayList;
import java.util.List;
import org.junit.Test;

public final class WearSmoochQueuePolicyTest {
    private static final long NOW = 2_000_000L;

    @Test public void currentRejectsExpiredAndFutureItems() {
        List<WearSmoochQueue.Pending> result = WearSmoochQueuePolicy.current(List.of(
                pending("expired", NOW - WearSmoochQueuePolicy.LIFETIME_MILLIS),
                pending("current", NOW - 1),
                pending("future", NOW + 1)), NOW);

        assertEquals(List.of("current"), ids(result));
    }

    @Test public void enqueueIsMutableBoundedAndDeduplicated() {
        List<WearSmoochQueue.Pending> values = new ArrayList<>();
        for (int index = 0; index < 7; index++) {
            values = WearSmoochQueuePolicy.enqueue(values, pending("id-" + index, NOW), NOW);
        }
        values = WearSmoochQueuePolicy.enqueue(values, pending("id-6", NOW), NOW);

        assertEquals(5, values.size());
        assertEquals(List.of("id-2", "id-3", "id-4", "id-5", "id-6"), ids(values));
    }

    @Test public void enqueueRejectsImpossibleFutureItemAndPurgesItFromInput() {
        List<WearSmoochQueue.Pending> values = WearSmoochQueuePolicy.enqueue(
                List.of(pending("stored-future", NOW + 5)),
                pending("new-future", NOW + 1), NOW);

        assertEquals(List.of(), values);
    }

    private static WearSmoochQueue.Pending pending(String id, long createdAt) {
        return new WearSmoochQueue.Pending(id, "😘", createdAt, "relationship", 3, 4);
    }

    private static List<String> ids(List<WearSmoochQueue.Pending> values) {
        return values.stream().map(WearSmoochQueue.Pending::operationId).toList();
    }
}
