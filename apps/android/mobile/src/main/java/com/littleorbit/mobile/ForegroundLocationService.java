package com.littleorbit.mobile;

import android.app.Notification;
import android.app.PendingIntent;
import android.app.Service;
import android.content.BroadcastReceiver;
import android.content.Context;
import android.content.Intent;
import android.content.IntentFilter;
import android.net.ConnectivityManager;
import android.net.Network;
import android.net.NetworkCapabilities;
import android.os.IBinder;
import androidx.annotation.Nullable;
import androidx.core.app.NotificationCompat;
import androidx.core.content.ContextCompat;
import com.littleorbit.data.LocationSampler;
import com.littleorbit.data.LocationCollectionWorker;
import dagger.hilt.android.AndroidEntryPoint;
import java.util.concurrent.Executors;
import java.util.concurrent.ScheduledExecutorService;
import java.util.concurrent.TimeUnit;
import javax.inject.Inject;

/** Visible two-minute location sampler started only from a user-visible activity. */
@AndroidEntryPoint
public final class ForegroundLocationService extends Service {
    private static final int NOTIFICATION_ID = 7301;
    private ScheduledExecutorService scheduler;
    private ConnectivityManager connectivity;
    private int lastTransport = -1;
    private long lastRecoveryAt;
    private final ConnectivityManager.NetworkCallback networkChanges =
            new ConnectivityManager.NetworkCallback() {
                @Override public void onAvailable(Network network) { recover(); }
                @Override public void onCapabilitiesChanged(
                        Network network, NetworkCapabilities capabilities) {
                    int transport = transport(capabilities);
                    if (transport != lastTransport) {
                        lastTransport = transport;
                        recover();
                    }
                }
            };
    private final BroadcastReceiver consentRevoked = new BroadcastReceiver() {
        @Override public void onReceive(Context context, Intent intent) { stopSelf(); }
    };
    @Inject LocationSampler sampler;
    @Inject TogetherHealthReporter healthReporter;

    /** Starts tracking while Android permits a visible-app foreground-service launch. */
    public static void start(Context context) {
        try {
            ContextCompat.startForegroundService(
                    context, new Intent(context, ForegroundLocationService.class));
        } catch (RuntimeException backgroundRestricted) {
            // The fifteen-minute WorkManager sampler remains active if the UI lost focus first.
        }
    }

    /** Stops foreground collection immediately. */
    public static void stop(Context context) {
        context.stopService(new Intent(context, ForegroundLocationService.class));
    }

    @Override
    public void onCreate() {
        super.onCreate();
        ContextCompat.registerReceiver(this, consentRevoked,
                new IntentFilter(LocationCollectionWorker.ACTION_COLLECTION_DISABLED),
                ContextCompat.RECEIVER_NOT_EXPORTED);
        startForeground(NOTIFICATION_ID, notification());
        scheduler = Executors.newSingleThreadScheduledExecutor(runnable -> {
            Thread thread = new Thread(runnable, "orbit-nearby-tracker");
            thread.setDaemon(true);
            return thread;
        });
        connectivity = getSystemService(ConnectivityManager.class);
        connectivity.registerDefaultNetworkCallback(networkChanges);
        scheduler.scheduleWithFixedDelay(this::sample, 0, 2, TimeUnit.MINUTES);
    }

    @Override
    public int onStartCommand(Intent intent, int flags, int startId) {
        return START_STICKY;
    }

    private void sample() {
        if (sampler.collect(true) == LocationSampler.Outcome.DISABLED) {
            stopSelf();
            return;
        }
        PartnerNotificationWorker.enqueue(this);
        healthReporter.publish();
    }

    private void recover() {
        long now = android.os.SystemClock.elapsedRealtime();
        if (scheduler == null || now - lastRecoveryAt < 30_000) return;
        lastRecoveryAt = now;
        scheduler.execute(this::sample);
    }

    private static int transport(NetworkCapabilities capabilities) {
        if (capabilities.hasTransport(NetworkCapabilities.TRANSPORT_WIFI)) return 1;
        if (capabilities.hasTransport(NetworkCapabilities.TRANSPORT_CELLULAR)) return 2;
        if (capabilities.hasTransport(NetworkCapabilities.TRANSPORT_ETHERNET)) return 3;
        return 0;
    }

    private Notification notification() {
        Intent open = new Intent(this, MainActivity.class)
                .addFlags(Intent.FLAG_ACTIVITY_SINGLE_TOP);
        PendingIntent content = PendingIntent.getActivity(
                this, 0, open, PendingIntent.FLAG_UPDATE_CURRENT | PendingIntent.FLAG_IMMUTABLE);
        return new NotificationCompat.Builder(this, NotificationChannels.LOCATION)
                .setSmallIcon(R.drawable.ic_nearby)
                .setContentTitle(getString(R.string.nearby_tracking_title))
                .setContentText(getString(R.string.nearby_tracking_message))
                .setContentIntent(content)
                .setOngoing(true)
                .setCategory(NotificationCompat.CATEGORY_SERVICE)
                .setVisibility(NotificationCompat.VISIBILITY_PRIVATE)
                .build();
    }

    @Override
    public void onDestroy() {
        if (scheduler != null) scheduler.shutdownNow();
        if (connectivity != null) connectivity.unregisterNetworkCallback(networkChanges);
        unregisterReceiver(consentRevoked);
        super.onDestroy();
    }

    @Nullable
    @Override
    public IBinder onBind(Intent intent) { return null; }
}
