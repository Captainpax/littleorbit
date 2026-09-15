package com.littleorbit.mobile;

import androidx.annotation.NonNull;
import com.google.firebase.messaging.FirebaseMessagingService;
import com.google.firebase.messaging.RemoteMessage;

/** Converts a content-free Firebase wake into an authenticated Little Orbit fetch. */
public final class LittleOrbitMessagingService extends FirebaseMessagingService {
    @Override
    public void onNewToken(@NonNull String token) {
        if (new NotificationDeviceStore(this).savePushToken(token)) {
            PartnerNotificationWorker.enqueue(this);
        }
    }

    @Override
    public void onMessageReceived(@NonNull RemoteMessage message) {
        if (!ContentFreePush.isWake(
                message.getData(), message.getNotification() != null)) return;
        PartnerNotificationWorker.enqueueExpedited(this);
    }

    @Override
    public void onDeletedMessages() {
        PartnerNotificationWorker.enqueue(this);
    }
}
