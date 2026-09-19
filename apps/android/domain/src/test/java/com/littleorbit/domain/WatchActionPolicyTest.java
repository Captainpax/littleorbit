package com.littleorbit.domain;

import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertTrue;

import org.junit.jupiter.api.Test;

final class WatchActionPolicyTest {
    private static final long NOW = 2_000_000;
    private static final String ID = "123e4567-e89b-12d3-a456-426614174000";

    @Test
    void acceptsOnlyExactCurrentAuthority() {
        assertTrue(WatchActionPolicy.authorized(request("node", 7, 11, NOW - 1_000),
                authority("node", 7, 11, true), NOW));
        assertFalse(WatchActionPolicy.authorized(request("other", 7, 11, NOW - 1_000),
                authority("node", 7, 11, true), NOW));
        assertFalse(WatchActionPolicy.authorized(request("node", 6, 11, NOW - 1_000),
                authority("node", 7, 11, true), NOW));
        assertFalse(WatchActionPolicy.authorized(request("node", 7, 10, NOW - 1_000),
                authority("node", 7, 11, true), NOW));
        assertFalse(WatchActionPolicy.authorized(request(
                "node", 7, 11, NOW - WatchProtocol.SMOOCH_LIFETIME_MILLIS),
                authority("node", 7, 11, true), NOW));
    }

    @Test
    void rejectsDisabledOrMalformedRequests() {
        assertFalse(WatchActionPolicy.authorized(request("node", 7, 11, NOW - 1_000),
                authority("node", 7, 11, false), NOW));
        WatchActionPolicy.Request invalid = new WatchActionPolicy.Request(
                "node", WatchProtocol.VERSION, 7, "relationship", 11,
                "not-a-uuid", "💌", NOW - 1_000);
        assertFalse(WatchActionPolicy.authorized(
                invalid, authority("node", 7, 11, true), NOW));
    }

    private static WatchActionPolicy.Request request(
            String node, long watchGeneration, long relationshipGeneration, long createdAt) {
        return new WatchActionPolicy.Request(
                node, WatchProtocol.VERSION, watchGeneration, "relationship",
                relationshipGeneration, ID, "😘", createdAt);
    }

    private static WatchActionPolicy.Authority authority(
            String node, long watchGeneration, long relationshipGeneration, boolean smooch) {
        return new WatchActionPolicy.Authority(
                true, smooch, node, watchGeneration, true, "relationship",
                relationshipGeneration);
    }
}
