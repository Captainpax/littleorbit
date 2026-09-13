package com.littleorbit.mobile;

import android.app.NotificationChannel;
import android.app.NotificationManager;
import android.content.Context;

/** Creates stable channels before any reminder or background poll needs them. */
final class NotificationChannels {
    static final String QUIZ = "quiz_updates";
    static final String COUNTDOWNS = "countdowns";
    static final String LOCATION = "nearby_time";
    static final String SMOOCHES = "smooches";
    static final String SHARED_SPACE = "shared_space";
    static final String UPDATES = "app_updates";

    private NotificationChannels() {}

    static void create(Context context) {
        NotificationManager manager = context.getSystemService(NotificationManager.class);
        manager.createNotificationChannel(new NotificationChannel(
                QUIZ, "Daily quiz", NotificationManager.IMPORTANCE_DEFAULT));
        manager.createNotificationChannel(new NotificationChannel(
                COUNTDOWNS,
                context.getString(R.string.countdowns),
                NotificationManager.IMPORTANCE_DEFAULT));
        manager.createNotificationChannel(new NotificationChannel(
                LOCATION,
                context.getString(R.string.nearby_tracking_channel),
                NotificationManager.IMPORTANCE_LOW));
        manager.createNotificationChannel(new NotificationChannel(
                SMOOCHES, context.getString(R.string.smooches),
                NotificationManager.IMPORTANCE_DEFAULT));
        manager.createNotificationChannel(new NotificationChannel(
                SHARED_SPACE, context.getString(R.string.shared_space_notifications),
                NotificationManager.IMPORTANCE_DEFAULT));
        manager.createNotificationChannel(new NotificationChannel(
                UPDATES, context.getString(R.string.app_updates),
                NotificationManager.IMPORTANCE_DEFAULT));
    }
}
