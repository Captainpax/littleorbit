package com.littleorbit.domain;

import java.util.List;

/** Versioned, content-minimal phone/Wear message contract. */
public final class WatchProtocol {
    public static final int VERSION = 1;
    public static final String STATUS = "/little-orbit/watch/status-v1";
    public static final String STATUS_REQUEST = "/little-orbit/watch/status-request-v1";
    public static final String SMOOCH = "/little-orbit/watch/smooch-v1";
    public static final String SMOOCH_RESULT = "/little-orbit/watch/smooch-result-v1";
    public static final String REFRESH = "/little-orbit/watch/refresh-v1";
    public static final List<String> SMOOCH_EMOJIS = List.of(
            "😘", "😍", "🤭", "😈", "🔥", "👀", "💖", "🐻", "🍑");
    public static final long SMOOCH_LIFETIME_MILLIS = 15L * 60 * 1_000;

    private WatchProtocol() {}

    /** True only for a server-approved Smooch choice. */
    public static boolean approvedEmoji(String value) {
        return SMOOCH_EMOJIS.contains(value);
    }

    /** True only while a watch action is inside the promised short delivery window. */
    public static boolean currentAction(long createdAt, long now) {
        return createdAt > 0 && createdAt <= now
                && createdAt + SMOOCH_LIFETIME_MILLIS > now;
    }
}
