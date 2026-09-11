package com.littleorbit.mobile;

/** Immutable values rendered by the home activity. */
public record HomeScreenState(
        String greeting,
        String togetherTime,
        String countdown,
        String freshness,
        boolean signedIn,
        boolean connected) {
    /** Initial state while no authorized cache is available. */
    public static HomeScreenState signedOut() {
        return new HomeScreenState(
                "Welcome to your orbit", "Not connected", "No countdown yet", "Sign in to sync", false, false);
    }

    /** Signed-in state before shared couple data is available locally. */
    public static HomeScreenState signedInWithoutCache() {
        return new HomeScreenState(
                "Your little orbit",
                "Not connected",
                "No countdown yet",
                "Signed in — connect or retry sync",
                true,
                false);
    }
}
