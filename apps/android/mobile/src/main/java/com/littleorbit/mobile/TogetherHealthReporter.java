package com.littleorbit.mobile;

import android.Manifest;
import android.app.NotificationManager;
import android.content.Context;
import android.content.Intent;
import android.content.IntentFilter;
import android.content.SharedPreferences;
import android.content.pm.PackageManager;
import android.net.ConnectivityManager;
import android.net.NetworkCapabilities;
import android.os.BatteryManager;
import android.os.Build;
import android.os.PowerManager;
import androidx.core.content.ContextCompat;
import com.littleorbit.data.local.LocationQueueDao;
import com.littleorbit.data.remote.TogetherTimeModels;
import com.littleorbit.data.repository.OrbitRepository;
import dagger.hilt.android.qualifiers.ApplicationContext;
import javax.inject.Inject;
import javax.inject.Singleton;

/** Publishes only explicitly opted-in, content-free collection health. */
@Singleton
final class TogetherHealthReporter {
    private static final String ENABLED = "enabled";
    private final Context context;
    private final OrbitRepository orbit;
    private final NotificationDeviceStore installation;
    private final LocationQueueDao queue;
    private final SharedPreferences preferences;

    @Inject TogetherHealthReporter(
            @ApplicationContext Context context,
            OrbitRepository orbit,
            NotificationDeviceStore installation,
            LocationQueueDao queue) {
        this.context = context;
        this.orbit = orbit;
        this.installation = installation;
        this.queue = queue;
        preferences = context.getSharedPreferences("together-health", Context.MODE_PRIVATE);
    }

    boolean enabled() {
        return preferences.getBoolean(ENABLED, false);
    }

    void setEnabled(boolean enabled) {
        preferences.edit().putBoolean(ENABLED, enabled).commit();
        if (enabled) publish();
        else orbit.deleteTogetherDeviceHealth(installation.id());
    }

    void publish() {
        if (!enabled() || !orbit.isSignedIn()) return;
        orbit.updateTogetherDeviceHealth(installation.id(), snapshot());
    }

    TogetherTimeModels.DeviceHealthUpdate snapshot() {
        Intent battery = context.registerReceiver(
                null, new IntentFilter(Intent.ACTION_BATTERY_CHANGED));
        int level = battery == null ? 0 : battery.getIntExtra(BatteryManager.EXTRA_LEVEL, 0);
        int scale = battery == null ? 100 : battery.getIntExtra(BatteryManager.EXTRA_SCALE, 100);
        int status = battery == null ? -1 : battery.getIntExtra(BatteryManager.EXTRA_STATUS, -1);
        boolean charging = status == BatteryManager.BATTERY_STATUS_CHARGING
                || status == BatteryManager.BATTERY_STATUS_FULL;
        int queued = Math.min(queue.count(), 1000);
        String network = networkTransport();
        return new TogetherTimeModels.DeviceHealthUpdate(
                Build.MANUFACTURER + " " + Build.MODEL,
                scale <= 0 ? 0 : Math.min(100, level * 100 / scale),
                charging,
                network,
                ContextCompat.checkSelfPermission(context, Manifest.permission.ACCESS_BACKGROUND_LOCATION)
                        == PackageManager.PERMISSION_GRANTED,
                batteryUnrestricted(),
                trackingNotificationVisible(),
                "offline".equals(network) || queued > 0 ? "waiting" : "working",
                queued);
    }

    private String networkTransport() {
        ConnectivityManager manager = context.getSystemService(ConnectivityManager.class);
        NetworkCapabilities value = manager.getNetworkCapabilities(manager.getActiveNetwork());
        if (value == null) return "offline";
        if (value.hasTransport(NetworkCapabilities.TRANSPORT_WIFI)) return "wifi";
        if (value.hasTransport(NetworkCapabilities.TRANSPORT_CELLULAR)) return "cellular";
        if (value.hasTransport(NetworkCapabilities.TRANSPORT_ETHERNET)) return "ethernet";
        return "other";
    }

    private boolean batteryUnrestricted() {
        PowerManager manager = context.getSystemService(PowerManager.class);
        return manager.isIgnoringBatteryOptimizations(context.getPackageName());
    }

    private boolean trackingNotificationVisible() {
        NotificationManager manager = context.getSystemService(NotificationManager.class);
        for (android.service.notification.StatusBarNotification item : manager.getActiveNotifications()) {
            if (item.getId() == 7301) return true;
        }
        return false;
    }
}
