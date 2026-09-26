package com.littleorbit.mobile;

/** Pure visibility and selection policy for the shared top-level navigation. */
final class OrbitNavigationState {
    private final OrbitDestination current;
    private final boolean signedIn;

    OrbitNavigationState(OrbitDestination current, boolean signedIn) {
        this.current = current;
        this.signedIn = signedIn;
    }

    boolean isSelected(OrbitDestination destination) {
        return current == destination;
    }

    boolean isVisible(OrbitDestination destination) {
        return signedIn
                || destination == OrbitDestination.HOME
                || destination == OrbitDestination.UPDATES;
    }
}
