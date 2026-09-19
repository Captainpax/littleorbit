package com.littleorbit.mobile;

import android.app.NotificationManager;
import android.content.Context;
import java.io.File;
import java.util.List;

/** Clears mobile-only relationship state after the data layer invalidates a relationship. */
final class RelationshipLocalPurge {
    private RelationshipLocalPurge() {}

    /** Removes relationship preferences, work, alerts, and temporary profile media. */
    static void clear(Context context) {
        Context app = context.getApplicationContext();
        new SetupChecklistController(app).clearAll();
        new NotificationSettingsStore(app).clear();
        new NotificationDeviceStore(app).clearForAccountChange();
        new CrashDiagnosticStore(app).clearForAccountChange();
        app.getSharedPreferences("smooch_settings", Context.MODE_PRIVATE).edit().clear().commit();
        app.getSharedPreferences("device_setup", Context.MODE_PRIVATE).edit().clear().commit();
        app.getSharedPreferences("together-health", Context.MODE_PRIVATE).edit().clear().commit();
        PartnerNotificationWorker.cancel(app);
        SmoochStatusWorker.schedule(app, false);
        CrashDiagnosticWorker.cancel(app);
        CountdownReminderScheduler.reconcile(app, List.of());
        ForegroundLocationService.stop(app);
        NotificationManager notifications = app.getSystemService(NotificationManager.class);
        if (notifications != null) notifications.cancelAll();
        deleteTree(new File(app.getCacheDir(), "profile-crops"));
    }

    private static void deleteTree(File target) {
        File[] children = target.listFiles();
        if (children != null) {
            for (File child : children) deleteTree(child);
        }
        if (target.exists()) target.delete();
    }
}
