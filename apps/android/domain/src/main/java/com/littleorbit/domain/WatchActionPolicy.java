package com.littleorbit.domain;

import java.util.UUID;

/** Pure authorization policy for a credential-free watch mutation request. */
public final class WatchActionPolicy {
    private WatchActionPolicy() {}

    /** Requires the exact current node and both current generation boundaries. */
    public static boolean authorized(Request request, Authority authority, long now) {
        if (request == null || authority == null) return false;
        return authority.watchEnabled() && authority.smoochEnabled()
                && authority.relationshipActive()
                && authority.selectedNodeId().equals(request.sourceNodeId())
                && request.protocol() == WatchProtocol.VERSION
                && authority.watchGeneration() == request.watchGeneration()
                && authority.relationshipId().equals(request.relationshipId())
                && authority.relationshipGeneration() == request.relationshipGeneration()
                && canonicalUuid(request.operationId())
                && WatchProtocol.approvedEmoji(request.emoji())
                && WatchProtocol.currentAction(request.createdAt(), now);
    }

    private static boolean canonicalUuid(String value) {
        try { return UUID.fromString(value).toString().equals(value); }
        catch (Exception invalid) { return false; }
    }

    /** Untrusted fields carried by one watch action. */
    public record Request(
            String sourceNodeId,
            int protocol,
            long watchGeneration,
            String relationshipId,
            long relationshipGeneration,
            String operationId,
            String emoji,
            long createdAt) {}

    /** Phone-owned current authorization state. */
    public record Authority(
            boolean watchEnabled,
            boolean smoochEnabled,
            String selectedNodeId,
            long watchGeneration,
            boolean relationshipActive,
            String relationshipId,
            long relationshipGeneration) {}
}
