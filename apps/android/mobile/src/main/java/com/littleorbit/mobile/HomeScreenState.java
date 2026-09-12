package com.littleorbit.mobile;

/** Immutable values rendered by the home activity. */
public record HomeScreenState(
        String greeting,
        String togetherTime,
        String nearbyTime,
        String countdown,
        String quizPrompt,
        String freshness,
        boolean signedIn,
        boolean connected) {
    /** Initial state while no authorized cache is available. */
    public static HomeScreenState signedOut() {
        return new HomeScreenState(
                "Welcome to your orbit",
                "Not connected",
                "Nearby time starts after pairing",
                "No countdown yet",
                "What made you smile today?",
                "Sign in to sync",
                false,
                false);
    }

    /** Signed-in state before shared couple data is available locally. */
    public static HomeScreenState signedInWithoutCache() {
        return new HomeScreenState(
                "Your little orbit",
                "Not connected",
                "Nearby time unavailable",
                "No countdown yet",
                "Today’s questions will appear after pairing",
                "Signed in — connect or retry sync",
                true,
                false);
    }

    /** Returns a copy with the current server-owned quiz prompt. */
    public HomeScreenState withQuizPrompt(String prompt) {
        return new HomeScreenState(
                greeting, togetherTime, nearbyTime, countdown, prompt,
                freshness, signedIn, connected);
    }
}
