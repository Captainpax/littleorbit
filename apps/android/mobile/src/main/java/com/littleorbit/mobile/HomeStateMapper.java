package com.littleorbit.mobile;

import com.littleorbit.data.local.DisplayCacheEntity;
import java.time.Duration;
import java.time.Instant;

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
        Instant updatedAt = Instant.ofEpochMilli(cache.updatedAtEpochMillis);
        boolean stale = updatedAt.plus(FRESHNESS_WINDOW).isBefore(now);
        return new HomeScreenState(
                "Your little orbit",
                Duration.ofSeconds(cache.togetherSeconds).toDays() + " days together",
                cache.nextCountdownTitle,
                stale ? "Estimate may be stale" : "Updated recently",
                signedIn);
    }
}
