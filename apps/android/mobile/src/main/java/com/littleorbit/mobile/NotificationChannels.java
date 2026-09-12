package com.littleorbit.mobile;

import android.app.NotificationChannel;
import android.app.NotificationManager;
import android.content.Context;

/** Creates stable channels before any reminder or background poll needs them. */
final class NotificationChannels {
    static final String QUIZ = "quiz_updates";
    static final String COUNTDOWNS = "countdowns";

    private NotificationChannels() {}

    static void create(Context context) {
        NotificationManager manager = context.getSystemService(NotificationManager.class);
        manager.createNotificationChannel(new NotificationChannel(
                QUIZ, "Daily quiz", NotificationManager.IMPORTANCE_DEFAULT));
        manager.createNotificationChannel(new NotificationChannel(
                COUNTDOWNS,
                context.getString(R.string.countdowns),
                NotificationManager.IMPORTANCE_DEFAULT));
    }
}
