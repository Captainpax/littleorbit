package com.littleorbit.mobile;

import com.littleorbit.data.local.DisplayCacheEntity;
import java.time.Duration;
import java.time.Instant;
import java.time.LocalDate;
import java.time.ZoneOffset;

/** Pure mapping from authentication and cache facts to immutable home state. */
final class HomeStateMapper {
    private static final Duration FRESHNESS_WINDOW = Duration.ofHours(6);

    private HomeStateMapper() {}

    /** Resolves an empty cache without confusing an authenticated account with a guest. */
    static HomeScreenState withoutCache(boolean signedIn) {
        return signedIn
                ? HomeScreenState.signedInWithoutCache()
                : HomeScreenState.signedOut();
    }

    /** Maps the privacy-limited cache using an injected time for deterministic tests. */
    static HomeScreenState fromCache(
            DisplayCacheEntity cache, boolean signedIn, Instant now) {
        String relationship = cache.relationshipStartEpochDay < 0
                ? "Pair to start your orbit"
                : Math.max(
                        0,
                        now.atZone(ZoneOffset.UTC).toLocalDate().toEpochDay()
                                - cache.relationshipStartEpochDay)
                        + " days together";
        String nearby = formatNearby(cache.nearbySeconds);
        return new HomeScreenState(
                "Your little orbit",
                relationship,
                nearby,
                cache.nextCountdownTitle,
                "Open today’s five questions",
                freshness(cache, now),
                signedIn,
                signedIn);
    }

    private static String formatNearby(long seconds) {
        long days = seconds / 86_400;
        long hours = (seconds % 86_400) / 3_600;
        long minutes = (seconds % 3_600) / 60;
        if (days > 0) {
            return days + "d " + hours + "h nearby · estimate";
        }
        return hours + "h " + minutes + "m nearby · estimate";
    }

    private static String freshness(DisplayCacheEntity cache, Instant now) {
        if (cache.cacheSyncedAtEpochMillis == 0
                || Instant.ofEpochMilli(cache.cacheSyncedAtEpochMillis)
                        .plus(FRESHNESS_WINDOW).isBefore(now)) {
            return "Cached data may be stale";
        }
        if (cache.nearbyProcessedAtEpochMillis == 0) {
            return "Nearby estimate has no samples yet";
        }
        Instant processed = Instant.ofEpochMilli(cache.nearbyProcessedAtEpochMillis);
        return processed.plus(FRESHNESS_WINDOW).isBefore(now)
                ? "Nearby estimate may be stale"
                : "Updated recently";
    }
}
