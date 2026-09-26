package com.littleorbit.mobile;

import android.app.Application;
import android.app.Activity;
import android.os.Bundle;
import androidx.hilt.work.HiltWorkerFactory;
import androidx.work.Configuration;
import com.littleorbit.data.security.SessionStore;
import dagger.hilt.android.HiltAndroidApp;
import javax.inject.Inject;

/** Application root for constructor-injected Android dependencies. */
@HiltAndroidApp
public final class LittleOrbitApplication extends Application implements Configuration.Provider {
    @Inject HiltWorkerFactory workerFactory;
    @Inject SessionStore sessions;
    @Inject ForegroundNotificationSocket notificationSocket;
    @Inject CrashDiagnosticStore crashDiagnostics;
    private int visibleActivities;

    @Override
    public void onCreate() {
        super.onCreate();
        NotificationChannels.create(this);
        installCrashCapture();
        UpdateDiscoveryWorker.schedule(this);
        registerActivityLifecycleCallbacks(new ForegroundNotifications());
        if (sessions.read().isPresent() && PermissionChecks.notificationsGranted(this)) {
            PartnerNotificationWorker.schedule(this, true);
            PartnerNotificationWorker.enqueue(this);
            CrashDiagnosticWorker.enqueue(this);
        } else {
            PartnerNotificationWorker.schedule(this, false);
        }
    }

    private void installCrashCapture() {
        Thread.UncaughtExceptionHandler previous = Thread.getDefaultUncaughtExceptionHandler();
        Thread.setDefaultUncaughtExceptionHandler((thread, failure) -> {
            try {
                crashDiagnostics.capture(failure, BuildConfig.VERSION_CODE, BuildConfig.VERSION_NAME);
            } catch (RuntimeException ignored) {
                // Crash reporting must never replace Android's original crash path.
            }
            if (previous != null) previous.uncaughtException(thread, failure);
        });
    }

    /** Routes WorkManager construction through Hilt without a global service locator. */
    @Override
    public Configuration getWorkManagerConfiguration() {
        return new Configuration.Builder().setWorkerFactory(workerFactory).build();
    }

    private final class ForegroundNotifications implements ActivityLifecycleCallbacks {
        @Override public void onActivityStarted(Activity activity) {
            if (visibleActivities++ == 0) notificationSocket.open();
        }

        @Override public void onActivityStopped(Activity activity) {
            visibleActivities = Math.max(0, visibleActivities - 1);
            if (visibleActivities == 0) notificationSocket.close();
        }

        @Override public void onActivityCreated(Activity activity, Bundle state) {}
        @Override public void onActivityResumed(Activity activity) {}
        @Override public void onActivityPaused(Activity activity) {}
        @Override public void onActivitySaveInstanceState(Activity activity, Bundle state) {}
        @Override public void onActivityDestroyed(Activity activity) {}
    }
}
