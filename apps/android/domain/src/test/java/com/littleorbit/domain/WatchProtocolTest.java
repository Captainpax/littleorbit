package com.littleorbit.domain;

import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertTrue;

import org.junit.jupiter.api.Test;

public final class WatchProtocolTest {
    @Test
    public void acceptsOnlyApprovedEmojiAndCurrentWindow() {
        long now = 1_000_000;
        assertTrue(WatchProtocol.approvedEmoji("😘"));
        assertFalse(WatchProtocol.approvedEmoji("💌"));
        assertTrue(WatchProtocol.currentAction(now - 1_000, now));
        assertFalse(WatchProtocol.currentAction(
                now - WatchProtocol.SMOOCH_LIFETIME_MILLIS, now));
        assertFalse(WatchProtocol.currentAction(now + 1, now));
    }
}
