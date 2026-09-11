package com.littleorbit.mobile;

/** Immutable values rendered by the home activity. */
public record HomeScreenState(
        String greeting,
        String togetherTime,
        String countdown,
        String freshness,
        boolean signedIn) {
    /** Initial state while no authorized cache is available. */
    public static HomeScreenState signedOut() {
        return new HomeScreenState(
                "Welcome to your orbit", "Not connected", "No countdown yet", "Sign in to sync", false);
    }

    /** State used when cached data remains available after a failed refresh. */
    public static HomeScreenState syncUnavailable() {
        return new HomeScreenState(
                "Your little orbit",
                "Estimate unavailable",
                "Cached countdown unavailable",
                "Offline — retry later",
                true);
    }
}
