package com.littleorbit.mobile;

import android.content.Context;
import android.content.SharedPreferences;
import com.littleorbit.data.remote.NotificationApiModels;

/** Installation cache of account notification choices for offline local reminders. */
final class NotificationSettingsStore {
    private final SharedPreferences values;

    NotificationSettingsStore(Context context) {
        values = context.getSharedPreferences("notification-settings", Context.MODE_PRIVATE);
    }

    void save(NotificationApiModels.Preferences prefs) {
        values.edit()
                .putBoolean("master", prefs.master)
                .putBoolean("smooches", prefs.smooches)
                .putBoolean("note_editing", prefs.noteEditing)
                .putBoolean("daily_quiz", prefs.dailyQuiz)
                .putBoolean("countdowns", prefs.countdowns)
                .putBoolean("together_time", prefs.togetherTime)
                .putBoolean("weekly_summary", prefs.weeklySummary)
                .apply();
    }

    boolean master() { return values.getBoolean("master", true); }
    boolean smooches() { return values.getBoolean("smooches", true); }
    boolean noteEditing() { return values.getBoolean("note_editing", true); }
    boolean dailyQuiz() { return values.getBoolean("daily_quiz", true); }
    boolean countdowns() { return values.getBoolean("countdowns", true); }
    boolean togetherTime() { return values.getBoolean("together_time", true); }
    boolean weeklySummary() { return values.getBoolean("weekly_summary", true); }

    void clear() { values.edit().clear().commit(); }
}
