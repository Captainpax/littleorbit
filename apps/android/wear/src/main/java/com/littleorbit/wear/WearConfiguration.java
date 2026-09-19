package com.littleorbit.wear;

import android.content.Context;
import android.content.SharedPreferences;

/** Target-scoped watch preferences sent by the signed-in phone. */
final class WearConfiguration {
    private static final String PREFERENCES = "little_orbit_watch_config_v1";

    private WearConfiguration() {}

    static void store(
            Context context,
            boolean photos,
            boolean countdownTitles,
            boolean smooches,
            String destination) {
        preferences(context).edit()
                .putBoolean("show_photos", photos)
                .putBoolean("show_countdown_titles", countdownTitles)
                .putBoolean("smooch_enabled", smooches)
                .putString("default_destination", validDestination(destination))
                .apply();
        if (!smooches) WearSmoochQueue.clear(context);
    }

    static State read(Context context) {
        SharedPreferences values = preferences(context);
        return new State(
                values.getBoolean("show_photos", true),
                values.getBoolean("show_countdown_titles", true),
                values.getBoolean("smooch_enabled", false),
                validDestination(values.getString("default_destination", "together")));
    }

    static void clear(Context context) {
        preferences(context).edit().clear().apply();
    }

    private static SharedPreferences preferences(Context context) {
        return context.getSharedPreferences(PREFERENCES, Context.MODE_PRIVATE);
    }

    private static String validDestination(String value) {
        if ("countdown".equals(value) || "smooch".equals(value)) return value;
        return "together";
    }

    record State(
            boolean showPhotos,
            boolean showCountdownTitles,
            boolean smoochEnabled,
            String defaultDestination) {}
}
