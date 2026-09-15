package com.littleorbit.mobile;

import java.util.Map;

/** Validates the complete allowlist for an untrusted FCM data message. */
final class ContentFreePush {
    private ContentFreePush() {}

    /** Accepts only Little Orbit's single opaque availability field. */
    static boolean isWake(Map<String, String> data, boolean hasNotificationPayload) {
        return !hasNotificationPayload
                && data.size() == 1
                && "notification.available".equals(data.get("signal"));
    }
}
