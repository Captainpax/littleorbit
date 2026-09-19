package com.littleorbit.wear;

import android.content.Context;
import android.content.res.Resources;

/** Localized presentation shared by the Wear launcher, tile, and complication. */
final class WearDisplayText {
    private final Context context;
    private final Resources resources;

    WearDisplayText(Context context) {
        this.context = context.getApplicationContext();
        resources = context.getResources();
    }

    String relationship(WearDisplayCache.State state) {
        return nearby(state);
    }

    String relationshipShort(WearDisplayCache.State state) {
        if (!state.available()) {
            return resources.getString(R.string.unavailable_short);
        }
        return state.nearbyHours() > 0
                ? resources.getString(R.string.nearby_hours_short, state.nearbyHours())
                : resources.getString(R.string.nearby_minutes_short,
                        state.nearbyMinutesRemainder());
    }

    String nearby(WearDisplayCache.State state) {
        if (!state.available()) return resources.getString(R.string.nearby_unavailable);
        return resources.getString(
                R.string.nearby_duration, state.nearbyHours(), state.nearbyMinutesRemainder());
    }

    String status(WearDisplayCache.State state) {
        if (!state.available()) return resources.getString(R.string.relationship_unavailable);
        if (state.stale()) return resources.getString(R.string.stale_open_phone);
        if (!WearConfiguration.read(context).showCountdownTitles()) {
            return resources.getString(R.string.next_countdown);
        }
        return state.countdownTitle == null || state.countdownTitle.isBlank()
                ? resources.getString(R.string.no_countdown)
                : state.countdownTitle;
    }

    String accessibility(WearDisplayCache.State state) {
        if (!state.available()) return resources.getString(R.string.relationship_unavailable_a11y);
        return resources.getString(
                R.string.relationship_summary, nearby(state), status(state));
    }

    String longComplication(WearDisplayCache.State state) {
        if (!state.available()) return resources.getString(R.string.open_phone_to_sync);
        int format = state.stale()
                ? R.string.complication_long_stale
                : R.string.complication_long;
        return resources.getString(format, nearby(state), status(state));
    }
}
