package com.littleorbit.mobile;

import android.Manifest;
import android.content.Context;
import android.content.pm.PackageManager;
import android.os.Build;
import androidx.core.app.NotificationManagerCompat;
import androidx.core.content.ContextCompat;

/** Central permission checks shared by setup, More, and background-work scheduling. */
final class PermissionChecks {
    private PermissionChecks() {}

    static boolean notificationsGranted(Context context) {
        boolean runtime = Build.VERSION.SDK_INT < 33
                || ContextCompat.checkSelfPermission(context, Manifest.permission.POST_NOTIFICATIONS)
                        == PackageManager.PERMISSION_GRANTED;
        return runtime && NotificationManagerCompat.from(context).areNotificationsEnabled();
    }

    static boolean fineLocationGranted(Context context) {
        return ContextCompat.checkSelfPermission(context, Manifest.permission.ACCESS_FINE_LOCATION)
                == PackageManager.PERMISSION_GRANTED;
    }

    static boolean backgroundLocationGranted(Context context) {
        return ContextCompat.checkSelfPermission(
                        context, Manifest.permission.ACCESS_BACKGROUND_LOCATION)
                == PackageManager.PERMISSION_GRANTED;
    }
}
