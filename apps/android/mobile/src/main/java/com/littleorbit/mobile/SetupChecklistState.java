package com.littleorbit.mobile;

/** Immutable Home setup summary; readiness is derived instead of permanently dismissed. */
public record SetupChecklistState(
        boolean pairingReady,
        boolean notificationsReady,
        boolean nearbyReady,
        boolean widgetReady,
        boolean watchReady,
        boolean collapsed) {
    /** Returns how many required setup areas are ready; the watch remains optional. */
    public int readyCount() {
        int count = pairingReady ? 1 : 0;
        count += notificationsReady ? 1 : 0;
        count += nearbyReady ? 1 : 0;
        return count + (widgetReady ? 1 : 0);
    }

    /** Returns whether every setup area is currently ready. */
    public boolean allReady() {
        return readyCount() == 4;
    }

    /** Keeps completed setup out of Home while allowing revoked requirements to return. */
    public boolean visibleOnHome() {
        return !allReady();
    }
}
