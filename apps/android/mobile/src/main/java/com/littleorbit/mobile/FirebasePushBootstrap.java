package com.littleorbit.mobile;

import android.content.Context;
import com.google.firebase.FirebaseApp;
import com.google.firebase.FirebaseOptions;
import com.google.firebase.messaging.FirebaseMessaging;

/** Initializes optional content-free FCM wake support without a committed config file. */
final class FirebasePushBootstrap {
    private FirebasePushBootstrap() {}

    /** Initializes Firebase only when all public Android project values were supplied. */
    static boolean initialize(Context context) {
        if (!configured()) return false;
        Context app = context.getApplicationContext();
        try {
            if (FirebaseApp.getApps(app).isEmpty()) {
                FirebaseOptions options = new FirebaseOptions.Builder()
                        .setApplicationId(BuildConfig.FIREBASE_APPLICATION_ID)
                        .setApiKey(BuildConfig.FIREBASE_API_KEY)
                        .setProjectId(BuildConfig.FIREBASE_PROJECT_ID)
                        .setGcmSenderId(BuildConfig.FIREBASE_SENDER_ID)
                        .build();
                FirebaseApp.initializeApp(app, options);
            }
            FirebaseMessaging.getInstance().setAutoInitEnabled(true);
            requestToken(app);
            return true;
        } catch (IllegalStateException invalidConfiguration) {
            return false;
        }
    }

    /** Refreshes the private installation address and schedules authenticated registration. */
    static void requestToken(Context context) {
        if (!configured() || FirebaseApp.getApps(context).isEmpty()) return;
        Context app = context.getApplicationContext();
        FirebaseMessaging.getInstance().getToken().addOnSuccessListener(token -> {
            if (new NotificationDeviceStore(app).savePushToken(token)) {
                PartnerNotificationWorker.enqueue(app);
            }
        });
    }

    /** Deletes one server-rejected address before requesting its replacement once. */
    static void rotateRejectedToken(Context context) {
        if (!configured() || FirebaseApp.getApps(context).isEmpty()) return;
        Context app = context.getApplicationContext();
        FirebaseMessaging.getInstance().deleteToken().addOnSuccessListener(
                ignored -> requestToken(app));
    }

    private static boolean configured() {
        return !BuildConfig.FIREBASE_APPLICATION_ID.isBlank()
                && !BuildConfig.FIREBASE_API_KEY.isBlank()
                && !BuildConfig.FIREBASE_PROJECT_ID.isBlank()
                && !BuildConfig.FIREBASE_SENDER_ID.isBlank();
    }
}
