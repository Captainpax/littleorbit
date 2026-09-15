package com.littleorbit.wear;

import android.content.Context;
import android.content.res.Resources;
import java.time.LocalDate;
import java.time.ZoneOffset;

/** Localized presentation shared by the Wear launcher, tile, and complication. */
final class WearDisplayText {
    private final Resources resources;

    WearDisplayText(Context context) {
        resources = context.getResources();
    }

    String relationship(WearDisplayCache.State state) {
        return relationship(state, LocalDate.now(ZoneOffset.UTC));
    }

    String relationship(WearDisplayCache.State state, LocalDate today) {
        if (!state.available()) return resources.getString(R.string.open_phone_to_sync);
        long days = state.relationshipDays(today);
        if (days < 0) return resources.getString(R.string.pair_date_unavailable);
        return resources.getQuantityString(R.plurals.relationship_days, quantity(days), days);
    }

    String relationshipShort(WearDisplayCache.State state) {
        long days = state.relationshipDays(LocalDate.now(ZoneOffset.UTC));
        return days < 0
                ? resources.getString(R.string.unavailable_short)
                : resources.getString(R.string.relationship_days_short, days);
    }

    String nearby(WearDisplayCache.State state) {
        if (!state.available()) return resources.getString(R.string.nearby_unavailable);
        return resources.getString(
                R.string.nearby_duration, state.nearbyHours(), state.nearbyMinutesRemainder());
    }

    String status(WearDisplayCache.State state) {
        if (!state.available()) return resources.getString(R.string.relationship_unavailable);
        if (state.stale()) return resources.getString(R.string.stale_open_phone);
        return state.countdownTitle == null || state.countdownTitle.isBlank()
                ? resources.getString(R.string.no_countdown)
                : state.countdownTitle;
    }

    String accessibility(WearDisplayCache.State state) {
        if (!state.available()) return resources.getString(R.string.relationship_unavailable_a11y);
        return resources.getString(
                R.string.relationship_summary,
                relationship(state), nearby(state), status(state));
    }

    String longComplication(WearDisplayCache.State state) {
        if (!state.available()) return resources.getString(R.string.open_phone_to_sync);
        int format = state.stale()
                ? R.string.complication_long_stale
                : R.string.complication_long;
        return resources.getString(format, relationship(state), nearby(state));
    }

    private static int quantity(long value) {
        return (int) Math.min(Integer.MAX_VALUE, Math.max(0, value));
    }
}
