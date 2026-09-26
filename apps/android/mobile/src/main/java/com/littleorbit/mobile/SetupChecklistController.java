package com.littleorbit.mobile;

import android.content.Context;
import android.content.SharedPreferences;

/** Persists only the per-couple checklist expansion state; readiness stays authoritative. */
public final class SetupChecklistController {
    private static final String STORE = "little-orbit-setup-checklist";
    private final SharedPreferences preferences;

    /** Creates the checklist controller for one application context. */
    public SetupChecklistController(Context context) {
        preferences = context.getApplicationContext()
                .getSharedPreferences(STORE, Context.MODE_PRIVATE);
    }

    /** Combines live readiness with the person's resumable expansion preference. */
    public SetupChecklistState state(
            String coupleId,
            boolean pairingReady,
            boolean notificationsReady,
            boolean nearbyReady,
            boolean widgetReady,
            boolean watchReady) {
        return new SetupChecklistState(
                pairingReady,
                notificationsReady,
                nearbyReady,
                widgetReady,
                watchReady,
                preferences.getBoolean(key(coupleId), false));
    }

    /** Collapses or expands the checklist without claiming an unfinished step is complete. */
    public void setCollapsed(String coupleId, boolean collapsed) {
        preferences.edit().putBoolean(key(coupleId), collapsed).apply();
    }

    /** Removes pair-scoped presentation state after unpair or account change. */
    public void clear(String coupleId) {
        preferences.edit().remove(key(coupleId)).apply();
    }

    /** Removes every relationship's presentation state after account invalidation. */
    public void clearAll() {
        preferences.edit().clear().commit();
    }

    private static String key(String coupleId) {
        return "collapsed_" + (coupleId == null ? "unpaired" : coupleId);
    }
}
